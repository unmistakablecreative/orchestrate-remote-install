import os
import re
import json
import argparse
CHUNK_MINUTES = 10
CHUNK_START_SECONDS = 120
MIDROLL_TIMESTAMP_PATTERN = '\\[(\\d{2}):(\\d{2}):(\\d{2})\\]'
PODCAST_INDEX = 'data/podcast_index.json'


def slugify(text):
    return text.lower().strip().replace('_', '-').replace(' ', '-')


def parse_timestamp(ts):
    match = re.match(MIDROLL_TIMESTAMP_PATTERN, ts)
    if not match:
        return None
    h, m, s = map(int, match.groups())
    return h * 3600 + m * 60 + s


def prep_transcript(params):
    filename = params.get('filename')
    if not filename:
        return {'status': 'error', 'message': 'Missing filename'}
    if not os.path.exists(filename):
        alt_path = os.path.join('uc_transcripts', filename)
        if os.path.exists(alt_path):
            filename = alt_path
        else:
            return {'status': 'error', 'message':
                f"File '{filename}' not found."}
    speaker = ''
    formatted_path = filename.replace('.md', '.formatted.md')
    with open(filename, 'r') as infile, open(formatted_path, 'w') as outfile:
        for line in infile:
            if '[' in line and re.search('\\*\\*[^:*]+:\\*\\*', line):
                name_match = re.search('\\*\\*([^:*]+):\\*\\*', line)
                if name_match:
                    new_speaker = name_match.group(1).strip()
                    if new_speaker != speaker:
                        speaker = new_speaker
                        outfile.write(f'\n### {speaker}\n')
            outfile.write(line)
    with open(formatted_path, 'r') as f:
        lines = f.readlines()
    chunks = []
    current_chunk = []
    chunk_start = CHUNK_START_SECONDS
    chunk_end = chunk_start + CHUNK_MINUTES * 60
    for line in lines:
        match = re.search(MIDROLL_TIMESTAMP_PATTERN, line)
        if not match:
            continue
        ts = match.group(0)
        seconds = parse_timestamp(ts)
        if seconds is None:
            continue
        if seconds > chunk_end:
            if current_chunk:
                chunks.append({'start': chunk_start, 'end': chunk_end,
                    'content': current_chunk})
            current_chunk = []
            chunk_start = chunk_end
            chunk_end += CHUNK_MINUTES * 60
        speaker_match = re.search('\\*\\*([^:*]+):\\*\\*', line)
        speaker = speaker_match.group(1).strip(
            ) if speaker_match else 'Unknown'
        text = line[line.find(']') + 1:].strip()
        current_chunk.append({'timestamp': ts, 'speaker': speaker, 'text':
            text})
    if current_chunk:
        chunks.append({'start': chunk_start, 'end': chunk_end, 'content':
            current_chunk})
    guest_key = slugify(os.path.basename(filename).replace('.md', ''))
    chunk_paths = []
    for i, chunk in enumerate(chunks):
        out_path = f'uc_transcripts/{guest_key}.part_{i + 1}.json'
        with open(out_path, 'w') as f:
            json.dump(chunk, f, indent=2)
        chunk_paths.append(out_path)
    index_path = f'uc_transcripts/{guest_key}.index.json'
    with open(index_path, 'w') as f:
        json.dump(chunk_paths, f, indent=2)
    return {'status': 'success', 'index_file': index_path, 'formatted_md':
        formatted_path}


def extract_midroll(params=None):
    import os
    filename = params.get('filename') if params else None
    start = '[00:25:00]'
    end = '[00:33:00]'
    if not filename:
        return {'status': 'error', 'message': 'Missing filename'}
    capturing = False
    lines = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                if start in line:
                    capturing = True
                if capturing:
                    lines.append(line.rstrip())
                if end in line and capturing:
                    break
        os.makedirs('midrolls', exist_ok=True)
        base_name = os.path.basename(filename).replace('.md', '')
        output_path = f'midrolls/{base_name}.midroll.md'
        with open(output_path, 'w') as out:
            for l in lines:
                out.write(l + '\n')
        return {'status': 'success', 'output_file': output_path}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def resolve_index():
    if not os.path.exists(PODCAST_INDEX):
        os.makedirs(os.path.dirname(PODCAST_INDEX), exist_ok=True)
        with open(PODCAST_INDEX, 'w') as f:
            json.dump({'entries': {}}, f)
    return PODCAST_INDEX


def add_episode_entry(params):
    key = slugify(params['entry_key'])
    title = params['title']
    summary = params['summary']
    midroll_time = params['midroll_time']
    try:
        minutes, seconds = map(int, midroll_time.strip().split(':'))
        total_seconds = round(minutes * 60 + seconds, 1)
        marker = f'midroll,{total_seconds}'
    except:
        return {'status': 'error', 'message': 'midroll_time must be mm:ss'}
    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)
    data['entries'][key] = {'title': title, 'summary': summary, 'alias':
        key, 'status': 'TBD', 'scheduled_publish_date': 'TBD', 'audio': key +
        '.mp3', 'markers': [marker]}
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return {'status': 'success', 'message': f"Entry '{key}' added."}


def update_episode_entry(params):
    key = slugify(params.get('entry_key'))
    new_data = params.get('new_data')
    if not key or not isinstance(new_data, dict):
        return {'status': 'error', 'message':
            'Missing entry_key or invalid new_data'}
    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)
    if key not in data.get('entries', {}):
        return {'status': 'error', 'message': f"Entry '{key}' not found"}
    data['entries'][key].update(new_data)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return {'status': 'success', 'message': f"Entry '{key}' updated."}


def delete_episode_entry(params):
    key = slugify(params.get('entry_key'))
    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)
    if key in data.get('entries', {}):
        del data['entries'][key]
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return {'status': 'success', 'message': f"Entry '{key}' deleted."}
    return {'status': 'error', 'message': f"Entry '{key}' not found."}


def list_episode_entries(params):
    path = 'data/podcast_index.json'
    if not os.path.exists(path):
        return {'status': 'error', 'message': 'Podcast index not found.'}
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return {'status': 'success', 'entries': list(data.get('entries', {}
            ).keys())}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def audit_transcript_for_ads(params):
    filename = params.get('filename')
    if not filename:
        return {'status': 'error', 'message': 'Missing filename'}
    if not os.path.exists(filename):
        alt_path = os.path.join('transcript_audit', filename)
        if os.path.exists(alt_path):
            filename = alt_path
        else:
            return {'status': 'error', 'message':
                f"File '{filename}' not found."}
    speaker = ''
    formatted_path = filename.replace('.md', '.formatted.md')
    with open(filename, 'r') as infile, open(formatted_path, 'w') as outfile:
        for line in infile:
            if '[' in line and re.search('\\*\\*[^:*]+:\\*\\*', line):
                name_match = re.search('\\*\\*([^:*]+):\\*\\*', line)
                if name_match:
                    new_speaker = name_match.group(1).strip()
                    if new_speaker != speaker:
                        speaker = new_speaker
                        outfile.write(f'\n### {speaker}\n')
            outfile.write(line)
    with open(formatted_path, 'r') as f:
        lines = f.readlines()
    chunks = []
    current_chunk = []
    chunk_start = CHUNK_START_SECONDS
    chunk_end = chunk_start + CHUNK_MINUTES * 60
    for line in lines:
        match = re.search(MIDROLL_TIMESTAMP_PATTERN, line)
        if not match:
            continue
        ts = match.group(0)
        seconds = parse_timestamp(ts)
        if seconds is None:
            continue
        if seconds > chunk_end:
            if current_chunk:
                chunks.append({'start': chunk_start, 'end': chunk_end,
                    'content': current_chunk})
            current_chunk = []
            chunk_start = chunk_end
            chunk_end += CHUNK_MINUTES * 60
        speaker_match = re.search('\\*\\*([^:*]+):\\*\\*', line)
        speaker = speaker_match.group(1).strip(
            ) if speaker_match else 'Unknown'
        text = line[line.find(']') + 1:].strip()
        current_chunk.append({'timestamp': ts, 'speaker': speaker, 'text':
            text})
    if current_chunk:
        chunks.append({'start': chunk_start, 'end': chunk_end, 'content':
            current_chunk})
    guest_key = slugify(os.path.basename(filename).replace('.md', ''))
    chunk_paths = []
    for i, chunk in enumerate(chunks):
        out_path = f'transcript_audit/{guest_key}.part_{i + 1}.json'
        with open(out_path, 'w') as f:
            json.dump(chunk, f, indent=2)
        chunk_paths.append(out_path)
    index_path = f'transcript_audit/{guest_key}.index.json'
    with open(index_path, 'w') as f:
        json.dump(chunk_paths, f, indent=2)
    return {'status': 'success', 'index_file': index_path, 'formatted_md':
        formatted_path}


def read_midroll_file(params):
    filename = params.get('filename')
    if not filename:
        return {'status': 'error', 'message': 'Missing filename'}
    path = f'midrolls/{filename}.midroll.md'
    if not os.path.exists(path):
        return {'status': 'error', 'message': f'Midroll file not found: {path}'
            }
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return {'status': 'success', 'content': content}


def read_index_file(params):
    filename = params.get('filename')
    if not filename:
        return {'status': 'error', 'message': 'Missing filename'}
    path = f'uc_transcripts/{filename}.index.json'
    if not os.path.exists(path):
        return {'status': 'error', 'message': f'Index file not found: {path}'}
    with open(path, 'r', encoding='utf-8') as f:
        content = json.load(f)
    return {'status': 'success', 'files': content}


def read_transcript_chunk(params):
    filename = params.get('filename')
    if not filename:
        return {'status': 'error', 'message': 'Missing filename'}
    path = f'uc_transcripts/{filename}.json'
    if not os.path.exists(path):
        return {'status': 'error', 'message': f'Chunk file not found: {path}'}
    with open(path, 'r', encoding='utf-8') as f:
        content = json.load(f)
    return {'status': 'success', 'content': content}


def process_episode_transcript(params):
    import os
    filename = params.get('filename')
    if not filename:
        return {'status': 'error', 'message': 'Missing filename'}
    prep_result = prep_transcript({'filename': filename})
    if prep_result.get('status') != 'success':
        return {'status': 'error', 'message': 'prep_transcript failed',
            'details': prep_result}
    formatted_md = prep_result.get('formatted_md')
    if not formatted_md or not os.path.exists(formatted_md):
        return {'status': 'error', 'message':
            'Formatted transcript missing after prep'}
    midroll_result = extract_midroll({'filename': formatted_md})
    if midroll_result.get('status') != 'success':
        return {'status': 'error', 'message': 'extract_midroll failed',
            'details': midroll_result}
    base_name = os.path.basename(filename).replace('.md', '')
    guest_key = slugify(base_name)
    return {'status': 'success', 'guest_key': guest_key, 'formatted_md':
        formatted_md, 'index_file':
        f'uc_transcripts/{guest_key}.index.json', 'midroll_file':
        midroll_result.get('output_file')}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params', type=str)
    args = parser.parse_args()

    router = {
        'slugify': slugify,
        'parse_timestamp': parse_timestamp,
        'prep_transcript': prep_transcript,
        'extract_midroll': extract_midroll,
        'resolve_index': resolve_index,
        'add_episode_entry': add_episode_entry,
        'update_episode_entry': update_episode_entry,
        'delete_episode_entry': delete_episode_entry,
        'list_episode_entries': list_episode_entries,
        'audit_transcript_for_ads': audit_transcript_for_ads,
        'read_midroll_file': read_midroll_file,
        'read_index_file': read_index_file,
        'read_transcript_chunk': read_transcript_chunk,
        'process_episode_transcript': process_episode_transcript
    }

    try:
        p = json.loads(args.params or '{}')
        if args.action in router:
            result = router[args.action](p)
        else:
            result = {'status': 'error', 'message': 'Invalid action'}
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({'status': 'error', 'message': str(e)}, indent=2))


if __name__ == '__main__':
    main()


