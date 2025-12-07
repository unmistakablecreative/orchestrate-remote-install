import os
import json
import time
import sys
import argparse
import subprocess
import glob
import fcntl
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

RULES_FILE = os.path.join(PROJECT_ROOT, 'data/automation_rules.json')
STATE_FILE = os.path.join(PROJECT_ROOT, 'data/automation_state.json')
EVENT_TYPES_FILE = os.path.join(PROJECT_ROOT, 'data/automation_events.json')
NDJSON_REGISTRY_FILE = os.path.join(PROJECT_ROOT, 'system_settings.ndjson')


class FileLock:
    """Exclusive file lock - prevents race conditions"""
    def __init__(self, filepath, timeout=30):
        self.filepath = str(filepath)
        self.timeout = timeout
        self.lock_file = None
        self.acquired = False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
    
    def acquire(self):
        lock_path = f"{self.filepath}.lock"
        os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                self.lock_file = open(lock_path, 'w')
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.acquired = True
                return True
            except BlockingIOError:
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                time.sleep(0.1)
                continue
            except Exception:
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                raise
        
        raise TimeoutError(f"Could not acquire lock")
    
    def release(self):
        if not self.acquired:
            return
        try:
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                self.lock_file = None
            lock_path = f"{self.filepath}.lock"
            if os.path.exists(lock_path):
                os.remove(lock_path)
            self.acquired = False
        except Exception:
            pass


def read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)


def write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def atomic_update_entry_status(file_path, entry_key, new_status, extra_fields=None):
    """Atomically update a single entry's status with FileLock."""
    with FileLock(file_path):
        data = read_json(file_path)
        if 'entries' not in data or entry_key not in data['entries']:
            return False
        data['entries'][entry_key]['status'] = new_status
        data['entries'][entry_key]['updated_at'] = datetime.now().isoformat()
        if extra_fields:
            for k, v in extra_fields.items():
                data['entries'][entry_key][k] = v
        write_json(file_path, data)
        return True


def load_tool_registry():
    tool_paths = {}
    if not os.path.exists(NDJSON_REGISTRY_FILE):
        return tool_paths
    try:
        with open(NDJSON_REGISTRY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('action') == '__tool__':
                        tool_name = entry.get('tool')
                        script_path = entry.get('script_path')
                        if tool_name and script_path:
                            tool_paths[tool_name] = script_path
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f'[REGISTRY ERROR] {e}', flush=True)
    return tool_paths


def resolve_context_values(params, context):
    if isinstance(params, dict):
        resolved_dict = {}
        for k, v in params.items():
            resolved_value = resolve_context_values(v, context)
            if isinstance(resolved_value, str) and resolved_value.startswith('{') and resolved_value.endswith('}') and resolved_value.count('{') == 1:
                placeholder = resolved_value[1:-1]
                if '.' in placeholder:
                    parts = placeholder.split('.')
                    value = context
                    resolved = False
                    try:
                        for part in parts:
                            if isinstance(value, dict):
                                value = value[part]
                            else:
                                break
                        else:
                            resolved = True
                            resolved_dict[k] = value
                    except (KeyError, TypeError):
                        pass
                    if not resolved:
                        continue
                elif placeholder not in context:
                    continue
                else:
                    resolved_dict[k] = resolved_value
            else:
                resolved_dict[k] = resolved_value
        return resolved_dict
    elif isinstance(params, list):
        return [resolve_context_values(item, context) for item in params]
    elif isinstance(params, str):
        import re
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, params)
        resolved = params
        for match in matches:
            if '.' in match:
                parts = match.split('.')
                value = context
                try:
                    for part in parts:
                        # Handle array indexing like participants[1]
                        if '[' in part and ']' in part:
                            key = part[:part.index('[')]
                            idx = int(part[part.index('[')+1:part.index(']')])
                            if isinstance(value, dict):
                                value = value[key][idx]
                            elif isinstance(value, list):
                                value = value[idx]
                            else:
                                raise KeyError
                        elif isinstance(value, dict):
                            value = value[part]
                        elif isinstance(value, list) and part.isdigit():
                            value = value[int(part)]
                        else:
                            raise KeyError
                    resolved = resolved.replace(f"{{{match}}}", str(value))
                except (KeyError, TypeError):
                    pass
            else:
                if match in context:
                    resolved = resolved.replace(f"{{{match}}}", str(context[match]))
        return resolved
    else:
        return params


def run_action(action, context):
    try:
        if 'steps' in action:
            return run_workflow_steps(action['steps'], context)
        raw_params = action.get('params', {})
        resolved_params = resolve_context_values(raw_params, context)
        registry = load_tool_registry()
        tool_name = action['tool']
        if tool_name in registry:
            final_params = resolved_params.copy() if isinstance(resolved_params, dict) else {}
            final_params["bypass_enforcement"] = "automation_engine"
            execution_hub_path = os.path.join(PROJECT_ROOT, 'execution_hub.py')
            cmd = ['python3', execution_hub_path, 'execute_task', '--params', json.dumps({"tool_name": tool_name, "action": action['action'], "params": final_params})]
        else:
            script = os.path.join(PROJECT_ROOT, f"tools/{tool_name}.py")
            cmd = ['python3', script, action['action'], '--params', json.dumps(resolved_params)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        if result.stdout:
            try:
                response = json.loads(result.stdout)
                status = response.get('status', '')
                if status == 'error':
                    print(f'❌ {tool_name}.{action["action"]}: {response.get("message", "Unknown error")}', flush=True)
                elif status == 'success':
                    msg = response.get('message', '')
                    if msg and msg not in ['ok', 'OK', 'Success']:
                        print(f'✅ {tool_name}.{action["action"]}: {msg}', flush=True)
                return response
            except (json.JSONDecodeError, KeyError):
                if result.stderr:
                    print(f'⚠️  {tool_name}.{action["action"]}: {result.stderr[:200]}', flush=True)
        return {}
    except Exception as e:
        print(f'❌ Action error: {str(e)}', flush=True)
        return {'status': 'error', 'message': str(e)}


def run_workflow_steps(steps, initial_context):
    context = initial_context.copy()
    previous_output = {}
    registry = load_tool_registry()
    for i, step in enumerate(steps):
        try:
            step_context = context.copy()
            step_context['prev'] = previous_output
            if step.get('type') == 'foreach':
                array_path = step.get('array')
                sub_steps = step.get('steps', [])
                try:
                    array_data = step_context
                    for part in array_path.split('.'):
                        array_data = array_data[part]
                    foreach_results = []
                    for idx, item in enumerate(array_data):
                        item_context = step_context.copy()
                        item_context['item'] = item
                        item_context['index'] = idx
                        for sub_step in sub_steps:
                            resolved_step = resolve_context_values(sub_step, item_context)
                            if resolved_step['tool'] in registry:
                                foreach_params = resolved_step['params'].copy() if isinstance(resolved_step['params'], dict) else {}
                                foreach_params["bypass_enforcement"] = "automation_engine"
                                execution_hub_path = os.path.join(PROJECT_ROOT, 'execution_hub.py')
                                cmd = ['python3', execution_hub_path, 'execute_task', '--params', json.dumps({"tool_name": resolved_step['tool'], "action": resolved_step['action'], "params": foreach_params})]
                            else:
                                script = os.path.join(PROJECT_ROOT, f"tools/{resolved_step['tool']}.py")
                                cmd = ['python3', script, resolved_step['action'], '--params', json.dumps(resolved_step['params'])]
                            result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
                            try:
                                sub_output = json.loads(result.stdout.strip())
                            except json.JSONDecodeError:
                                sub_output = {"status": "completed", "output": result.stdout.strip()}
                            item_context['prev'] = sub_output
                        foreach_results.append(sub_output)
                    previous_output = {"results": foreach_results, "processed_count": len(foreach_results)}
                    continue
                except Exception as e:
                    return {"status": "error", "message": f"Foreach step failed: {str(e)}"}
            raw_params = step.get('params', {})
            resolved_params = resolve_context_values(raw_params, step_context)
            if step['tool'] in registry:
                final_params = resolved_params.copy() if isinstance(resolved_params, dict) else {}
                final_params["bypass_enforcement"] = "automation_engine"
                execution_hub_path = os.path.join(PROJECT_ROOT, 'execution_hub.py')
                cmd = ['python3', execution_hub_path, 'execute_task', '--params', json.dumps({"tool_name": step['tool'], "action": step['action'], "params": final_params})]
            else:
                script = os.path.join(PROJECT_ROOT, f"tools/{step['tool']}.py")
                cmd = ['python3', script, step['action'], '--params', json.dumps(resolved_params)]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
            try:
                step_output = json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                step_output = {"status": "completed", "output": result.stdout.strip()}
            previous_output = step_output
            if step_output.get("status") == "error":
                return step_output
        except Exception as e:
            return {"status": "error", "message": f"Step {i+1} execution failed: {str(e)}"}
    return previous_output


def process_queue_entry_with_lock(file_path, key, entry, rule):
    """Process a single queue entry with FileLock to prevent duplicates."""
    
    # ATOMIC: Check status and mark as processing in one operation
    with FileLock(file_path):
        data = read_json(file_path)
        if 'entries' not in data or key not in data['entries']:
            print(f'[SKIP] {key} - entry not found', flush=True)
            return False
        
        current_status = data['entries'][key].get('status', '')
        
        # Skip if already processing, processed, or failed
        if current_status in ('processing', 'processed', 'failed'):
            print(f'[SKIP] {key} - already {current_status}', flush=True)
            return False
        
        # Mark as processing
        data['entries'][key]['status'] = 'processing'
        data['entries'][key]['updated_at'] = datetime.now().isoformat()
        write_json(file_path, data)
    
    print(f'[LOCKED] {key} -> processing', flush=True)
    
    # Build context from entry
    context = {"entry_key": key}
    for k, v in entry.items():
        if k != "entry_key":
            context[k] = v
    
    # Run the action
    try:
        result = run_action(rule["action"], context)
        
        # Check if workflow succeeded
        if isinstance(result, dict) and result.get('status') == 'error':
            atomic_update_entry_status(file_path, key, 'failed', {'error': result.get('message', 'Unknown error')})
            print(f'[FAILED] {key}: {result.get("message")}', flush=True)
            return False
        
        # Success - verify status
        with FileLock(file_path):
            current_data = read_json(file_path)
            current_status = current_data.get('entries', {}).get(key, {}).get('status')
            if current_status == 'processing':
                current_data['entries'][key]['status'] = 'processed'
                current_data['entries'][key]['updated_at'] = datetime.now().isoformat()
                write_json(file_path, current_data)
                print(f'[PROCESSED] {key} (auto-marked)', flush=True)
            else:
                print(f'[PROCESSED] {key}', flush=True)
        
        return True
        
    except Exception as e:
        atomic_update_entry_status(file_path, key, 'failed', {'error': str(e)})
        print(f'[ERROR] {key}: {str(e)}', flush=True)
        return False


def engine_loop():
    print(json.dumps({'status': 'ok', 'message': 'Automation Engine is running'}), flush=True)
    state = read_json(STATE_FILE)
    processed_this_session = set()

    while True:
        rules_data = read_json(RULES_FILE).get('rules', {})

        file_rules = {}
        for rule_key, rule in rules_data.items():
            trigger = rule.get('trigger', {})
            trig_type = trigger.get('type')
            file_path = trigger.get('file')
            if file_path and not os.path.isabs(file_path):
                file_path = os.path.join(PROJECT_ROOT, file_path)
            if trig_type in ('entry_added', 'entry_updated'):
                if file_path not in file_rules:
                    file_rules[file_path] = {'entry_added': [], 'entry_updated': []}
                file_rules[file_path][trig_type].append((rule_key, rule))

        for file_path, type_rules in file_rules.items():
            new_data = read_json(file_path)
            old_data = state.get(file_path, {})
            new_entries = new_data.get('entries', {})
            old_entries = old_data.get('entries', {})

            for rule_key, rule in type_rules['entry_added']:
                test_expr = read_json(EVENT_TYPES_FILE).get('entry_added', {}).get('test')
                if not test_expr:
                    continue
                    
                for key, new_entry in new_entries.items():
                    current_status = new_entry.get('status', '')
                    if current_status in ('processed', 'processing', 'failed'):
                        continue
                    
                    session_key = f"{file_path}:{key}:added"
                    if session_key in processed_this_session:
                        continue
                    
                    old_entry = old_entries.get(key, {})
                    ctx = {'key': key, 'old_entry': old_entry, 'new_entry': new_entry}
                    
                    try:
                        if not eval(test_expr, {}, ctx):
                            continue
                    except:
                        continue
                    
                    rule_condition = rule.get("condition")
                    if rule_condition:
                        try:
                            if not eval(rule_condition, {}, ctx):
                                continue
                        except:
                            continue
                    
                    processed_this_session.add(session_key)
                    process_queue_entry_with_lock(file_path, key, new_entry, rule)

            for rule_key, rule in type_rules['entry_updated']:
                test_expr = read_json(EVENT_TYPES_FILE).get('entry_updated', {}).get('test')
                if not test_expr:
                    continue
                    
                for key, new_entry in new_entries.items():
                    if key not in old_entries:
                        continue
                    
                    current_status = new_entry.get('status', '')
                    if current_status in ('processing', 'failed'):
                        continue
                    
                    old_entry = old_entries[key]
                    ctx = {'key': key, 'old_entry': old_entry, 'new_entry': new_entry}
                    
                    try:
                        if not eval(test_expr, {}, ctx):
                            continue
                    except:
                        continue
                    
                    # Use status + rule_key for deduplication, NOT updated_at timestamp
                    # This prevents duplicate fires when updated_at changes between polls
                    entry_status = new_entry.get('status', '')
                    session_key = f"{file_path}:{key}:{rule_key}:{entry_status}"
                    if session_key in processed_this_session:
                        continue
                    
                    rule_condition = rule.get("condition")
                    if rule_condition:
                        try:
                            if not eval(rule_condition, {}, ctx):
                                continue
                        except:
                            continue
                    
                    processed_this_session.add(session_key)
                    context = {"entry_key": key}
                    for k, v in new_entry.items():
                        if k != "entry_key":
                            context[k] = v
                    print(f'[PROCESSING] {rule_key} -> {key}', flush=True)
                    run_action(rule["action"], context)

            state[file_path] = new_data

        for rule_key, rule in rules_data.items():
            trigger = rule.get('trigger', {})
            trig_type = trigger.get('type')
            
            if trig_type == 'time':
                now = datetime.now()
                current_time_str = now.strftime('%H:%M')
                if trigger.get('at') == current_time_str or trigger.get('daily') == current_time_str:
                    print(f'[TRIGGER] {rule_key} (time)', flush=True)
                    result = run_action(rule['action'], {})
                    # Handle post_action with for_each
                    if 'post_action' in rule and result:
                        post = rule['post_action']
                        if 'for_each' in post:
                            array_key = post['for_each']
                            items = result.get(array_key, [])
                            condition = post.get('condition')
                            # Handle dict (iterate key-value pairs) or list
                            if isinstance(items, dict):
                                items_iter = [(k, v) for k, v in items.items()]
                            else:
                                items_iter = [(None, item) for item in items]
                            for item_key, item in items_iter:
                                # Check condition if exists
                                if condition:
                                    try:
                                        if not eval(condition, {"item": item, "datetime": datetime}):
                                            continue
                                    except Exception as e:
                                        print(f'[CONDITION ERROR] {e}', flush=True)
                                        continue
                                # Run the action with item context (include key for dicts)
                                item_context = {'item': item, 'item_key': item_key}
                                run_action(post['action'], item_context)

            elif trig_type == 'interval':
                interval_minutes = trigger.get('minutes', 5)
                last_execution = state.get('interval_executions', {}).get(rule_key)
                should_run = False
                if last_execution is None:
                    should_run = True
                else:
                    now = datetime.now()
                    last_time = datetime.fromisoformat(last_execution)
                    minutes_passed = (now - last_time).total_seconds() / 60
                    if minutes_passed >= interval_minutes:
                        should_run = True
                if should_run:
                    print(f'[TRIGGER] {rule_key} (interval)', flush=True)
                    run_action(rule['action'], {})
                    if 'interval_executions' not in state:
                        state['interval_executions'] = {}
                    state['interval_executions'][rule_key] = datetime.now().isoformat()

        write_json(STATE_FILE, state)
        
        if len(processed_this_session) > 10000:
            processed_this_session.clear()
        
        time.sleep(5)


def add_rule(params):
    rule_key = params.get('rule_key')
    rule_data = params.get('rule')
    if not rule_key or not isinstance(rule_data, dict):
        return {'status': 'error', 'message': 'rule_key and rule dict required'}
    data = read_json(RULES_FILE)
    if 'rules' not in data:
        data['rules'] = {}
    if rule_key in data['rules']:
        return {'status': 'error', 'message': f'Rule "{rule_key}" already exists'}
    data['rules'][rule_key] = rule_data
    write_json(RULES_FILE, data)
    return {'status': 'success', 'message': f'Rule "{rule_key}" added.'}


def update_rule(params):
    rule_key = params.get('rule_key')
    rule_data = params.get('rule')
    if not rule_key or not isinstance(rule_data, dict):
        return {'status': 'error', 'message': 'rule_key and rule dict required'}
    data = read_json(RULES_FILE)
    if 'rules' not in data or rule_key not in data['rules']:
        return {'status': 'error', 'message': f'Rule "{rule_key}" not found'}
    data['rules'][rule_key] = rule_data
    write_json(RULES_FILE, data)
    return {'status': 'success', 'message': f'Rule "{rule_key}" updated.'}


def delete_rule(params):
    rule_key = params.get('rule_key')
    if not rule_key:
        return {'status': 'error', 'message': 'rule_key required'}
    data = read_json(RULES_FILE)
    if 'rules' not in data or rule_key not in data['rules']:
        return {'status': 'error', 'message': f'Rule "{rule_key}" not found'}
    del data['rules'][rule_key]
    write_json(RULES_FILE, data)
    return {'status': 'success', 'message': f'Rule "{rule_key}" deleted.'}


def get_rule(params):
    rule_key = params.get('rule_key')
    if not rule_key:
        return {'status': 'error', 'message': 'rule_key required'}
    data = read_json(RULES_FILE)
    rules = data.get('rules', {})
    if rule_key not in rules:
        return {'status': 'error', 'message': f'Rule "{rule_key}" not found'}
    return {'status': 'success', 'rule_key': rule_key, 'rule': rules[rule_key]}


def get_rules(params):
    data = read_json(RULES_FILE)
    rules = data.get('rules', {})
    return {'status': 'ok', 'rules': rules, 'rule_count': len(rules)}


def list_rules(params):
    data = read_json(RULES_FILE)
    rules = data.get('rules', {})
    rule_list = []
    for rule_key, rule_data in rules.items():
        trigger = rule_data.get('trigger', {})
        rule_list.append({'rule_key': rule_key, 'trigger_type': trigger.get('type'), 'trigger_file': trigger.get('file'), 'has_condition': 'condition' in rule_data})
    return {'status': 'ok', 'rules': rule_list, 'rule_count': len(rule_list)}


def add_event_type(params):
    key = params.get('key')
    expr = params.get('test')
    if not key or not expr:
        return {'status': 'error', 'message': 'key and test required'}
    data = read_json(EVENT_TYPES_FILE)
    data[key] = {'test': expr}
    write_json(EVENT_TYPES_FILE, data)
    return {'status': 'success', 'message': f"Event type '{key}' added."}


def update_event_type(params):
    key = params.get('key')
    expr = params.get('test')
    if not key or not expr:
        return {'status': 'error', 'message': 'key and test required'}
    data = read_json(EVENT_TYPES_FILE)
    if key not in data:
        return {'status': 'error', 'message': 'Event type not found.'}
    data[key]['test'] = expr
    write_json(EVENT_TYPES_FILE, data)
    return {'status': 'success', 'message': f"Event type '{key}' updated."}


def get_event_types(params):
    data = read_json(EVENT_TYPES_FILE)
    return {'status': 'ok', 'events': data}


def dispatch_event(event_key, payload):
    rules_data = read_json(RULES_FILE).get('rules', {})
    matched = []
    for rule_key, rule in rules_data.items():
        trigger = rule.get('trigger', {})
        if trigger.get('type') == 'event' and trigger.get('event_key') == event_key:
            context = payload.copy()
            run_action(rule['action'], context)
            matched.append(rule_key)
    return {'status': 'ok', 'message': f'{len(matched)} event-based rule(s) triggered.'}


def retry_failed(params):
    """Reset failed entries back to queued for retry."""
    file_path = params.get('file')
    if not file_path:
        return {'status': 'error', 'message': 'file parameter required'}
    if not os.path.isabs(file_path):
        file_path = os.path.join(PROJECT_ROOT, file_path)
    
    with FileLock(file_path):
        data = read_json(file_path)
        entries = data.get('entries', {})
        reset_count = 0
        
        for key, entry in entries.items():
            if entry.get('status') == 'failed':
                entry['status'] = 'queued'
                entry['updated_at'] = datetime.now().isoformat()
                if 'error' in entry:
                    del entry['error']
                reset_count += 1
        
        write_json(file_path, data)
    
    return {'status': 'success', 'message': f'Reset {reset_count} failed entries to queued'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}

    if args.action == 'run_engine':
        result = engine_loop()
    elif args.action == 'add_rule':
        result = add_rule(params)
    elif args.action == 'update_rule':
        result = update_rule(params)
    elif args.action == 'delete_rule':
        result = delete_rule(params)
    elif args.action == 'get_rule':
        result = get_rule(params)
    elif args.action == 'get_rules':
        result = get_rules(params)
    elif args.action == 'list_rules':
        result = list_rules(params)
    elif args.action == 'add_event_type':
        result = add_event_type(params)
    elif args.action == 'update_event_type':
        result = update_event_type(params)
    elif args.action == 'dispatch_event':
        result = dispatch_event(params.get('event_key'), params)
    elif args.action == 'get_event_types':
        result = get_event_types(params)
    elif args.action == 'retry_failed':
        result = retry_failed(params)
    else:
        result = {'status': 'error', 'message': f'Unknown action {args.action}'}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()