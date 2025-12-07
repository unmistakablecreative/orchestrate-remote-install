import json
import os
import requests
import uuid

BASE_URL = "https://canvas.instructure.com"
CREDS = json.load(open("tools/credentials.json"))
API_KEY = CREDS.get("CANVAS_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

BASE_PATH = "data/canvas"
MODULE_DIR = os.path.join(BASE_PATH, "modules")
LECTURE_DIR = os.path.join(BASE_PATH, "lectures")
LAB_DIR = os.path.join(BASE_PATH, "labs")
QUIZ_DIR = os.path.join(BASE_PATH, "quizzes")
COURSE_DIR = os.path.join(BASE_PATH, "courses")

os.makedirs(MODULE_DIR, exist_ok=True)
os.makedirs(LECTURE_DIR, exist_ok=True)
os.makedirs(LAB_DIR, exist_ok=True)
os.makedirs(QUIZ_DIR, exist_ok=True)
os.makedirs(COURSE_DIR, exist_ok=True)

# ============================================================================
# UNIFIED FUNCTIONS (New API - 4 actions for all entity types)
# ============================================================================

def create_draft(params):
    """
    Unified create function for all entity types.

    Args:
        entity_type (str): One of: module, lecture, lab, quiz, course
        entity_name (str): Name of the entity
        **kwargs: Entity-specific parameters

    Returns:
        dict: Status and message
    """
    entity_type = params.get("entity_type")
    entity_name = params.get("entity_name")

    if not entity_type or not entity_name:
        return {"status": "error", "message": "Missing required parameters: entity_type, entity_name"}

    # Route to appropriate internal create function
    if entity_type == "module":
        return _create_module_internal(entity_name, params)
    elif entity_type == "lecture":
        return _create_lecture_internal(entity_name, params)
    elif entity_type == "lab":
        return _create_lab_internal(entity_name, params)
    elif entity_type == "quiz":
        return _create_quiz_internal(entity_name, params)
    elif entity_type == "course":
        return _create_course_internal(entity_name, params)
    else:
        return {"status": "error", "message": f"Unknown entity_type: {entity_type}"}

def view_draft(params):
    """
    Unified view function for all entity types.

    Args:
        entity_type (str): One of: module, lecture, lab, quiz, course
        entity_name (str): Name of the entity

    Returns:
        dict: Status and entity data
    """
    entity_type = params.get("entity_type")
    entity_name = params.get("entity_name")

    if not entity_type or not entity_name:
        return {"status": "error", "message": "Missing required parameters: entity_type, entity_name"}

    # Route to appropriate internal view function
    if entity_type == "module":
        return _view_module_internal(entity_name)
    elif entity_type == "lecture":
        return _view_lecture_internal(entity_name)
    elif entity_type == "lab":
        return _view_lab_internal(entity_name)
    elif entity_type == "quiz":
        return _view_quiz_internal(entity_name)
    elif entity_type == "course":
        return _view_course_internal(entity_name)
    else:
        return {"status": "error", "message": f"Unknown entity_type: {entity_type}"}

def edit_draft(params):
    """
    Unified edit function for all entity types.

    Args:
        entity_type (str): One of: module, lecture, lab, quiz, course
        entity_name (str): Name of the entity
        updates (dict): Dictionary of fields to update

    Returns:
        dict: Status and message
    """
    entity_type = params.get("entity_type")
    entity_name = params.get("entity_name")
    updates = params.get("updates", {})

    if not entity_type or not entity_name:
        return {"status": "error", "message": "Missing required parameters: entity_type, entity_name"}

    # Route to appropriate internal edit function
    if entity_type == "module":
        return _edit_module_internal(entity_name, updates)
    elif entity_type == "lecture":
        return _edit_lecture_internal(entity_name, updates)
    elif entity_type == "lab":
        return _edit_lab_internal(entity_name, updates)
    elif entity_type == "quiz":
        return _edit_quiz_internal(entity_name, updates)
    elif entity_type == "course":
        return _edit_course_internal(entity_name, updates)
    else:
        return {"status": "error", "message": f"Unknown entity_type: {entity_type}"}

def publish(params):
    """
    Unified publish function for all entity types.

    Args:
        entity_type (str): One of: module, lecture, lab, quiz, course
        entity_name (str): Name of the entity
        course_id (str): Canvas course ID
        **kwargs: Entity-specific parameters

    Returns:
        dict: Status and publish results
    """
    entity_type = params.get("entity_type")
    entity_name = params.get("entity_name")
    course_id = params.get("course_id")

    if not entity_type or not entity_name:
        return {"status": "error", "message": "Missing required parameters: entity_type, entity_name"}

    # Route to appropriate internal publish function
    if entity_type == "module":
        if not course_id:
            return {"status": "error", "message": "Missing required parameter: course_id"}
        return _publish_module_internal(entity_name, course_id, params)
    elif entity_type == "lecture":
        if not course_id:
            return {"status": "error", "message": "Missing required parameter: course_id"}
        return _publish_lecture_internal(entity_name, course_id)
    elif entity_type == "lab":
        if not course_id:
            return {"status": "error", "message": "Missing required parameter: course_id"}
        return _publish_lab_internal(entity_name, course_id)
    elif entity_type == "quiz":
        if not course_id:
            return {"status": "error", "message": "Missing required parameter: course_id"}
        return _publish_quiz_internal(entity_name, course_id)
    elif entity_type == "course":
        # Course publishing is special - it's a multi-step workflow
        return publish_course({"course_name": entity_name, "course_id": course_id})
    else:
        return {"status": "error", "message": f"Unknown entity_type: {entity_type}"}

# ============================================================================
# INTERNAL HELPER FUNCTIONS (Not exposed in schema)
# ============================================================================

def _create_module_internal(module_name, params):
    """Internal helper for module creation"""
    path = os.path.join(MODULE_DIR, f"{module_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Module '{module_name}' already exists."}

    title = params.get("title") or module_name.replace("_", " ").title()
    data = {
        "title": title,
        "lectures": [],
        "labs": [],
        "quizzes": []
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Module draft '{module_name}' created."}

def _create_lecture_internal(lecture_name, params):
    """Internal helper for lecture creation"""
    json_name = lecture_name.replace(os.path.splitext(lecture_name)[1], ".json")
    path = os.path.join(LECTURE_DIR, json_name)

    if os.path.exists(path):
        return {"status": "error", "message": f"Lecture draft '{json_name}' already exists."}

    with open("data/canvas/templates/lecture_template.json") as f:
        draft = json.load(f)

    draft["filename"] = lecture_name

    with open(path, "w") as f:
        json.dump(draft, f, indent=2)

    return {"status": "success", "message": f"Lecture draft for '{lecture_name}' created."}

def _create_lab_internal(lab_name, params):
    """Internal helper for lab creation"""
    path = os.path.join(LAB_DIR, f"{lab_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Lab draft '{lab_name}' already exists."}

    with open("data/canvas/templates/lab_template.json") as f:
        draft = json.load(f)

    draft["name"] = params.get("title", lab_name)
    draft["due_at"] = params.get("due_at", "")
    draft["file_name"] = params.get("file_name", "")
    draft["description"] = params.get("description", "")
    draft["points_possible"] = params.get("points_possible", 100)
    draft["submission_types"] = params.get("submission_types", ["online_upload"])
    draft["published"] = params.get("published", True)

    with open(path, "w") as f:
        json.dump(draft, f, indent=2)

    return {"status": "success", "message": f"Lab draft '{lab_name}' created."}

def _create_quiz_internal(quiz_name, params):
    """Internal helper for quiz creation"""
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' already exists."}

    with open("data/canvas/templates/quiz_template.json") as f:
        draft = json.load(f)

    draft["title"] = params.get("title", quiz_name.replace("_", " ").title())
    if "due_at" in params:
        draft["due_at"] = params["due_at"]
    if "quiz_type" in params:
        draft["quiz_type"] = params["quiz_type"]
    if "published" in params:
        draft["published"] = params["published"]
    if "description" in params:
        draft["description"] = params["description"]
    if "questions" in params:
        draft["questions"] = params["questions"]

    with open(path, "w") as f:
        json.dump(draft, f, indent=2)

    return {"status": "success", "message": f"Quiz draft '{quiz_name}' created."}

def _create_course_internal(course_name, params):
    """Internal helper for course creation"""
    path = os.path.join(COURSE_DIR, f"{course_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Course draft '{course_name}' already exists."}

    data = {
        "course_name": course_name,
        "title": params.get("title", course_name.replace("_", " ").title()),
        "modules": []
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Course draft '{course_name}' created."}

def _view_module_internal(module_name):
    """Internal helper for viewing module"""
    path = os.path.join(MODULE_DIR, f"{module_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": "Module does not exist."}
    data = json.load(open(path))
    return {"status": "success", "module": data}

def _view_lecture_internal(lecture_name):
    """Internal helper for viewing lecture"""
    path = os.path.join(LECTURE_DIR, f"{lecture_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lecture draft '{lecture_name}' not found."}
    data = json.load(open(path))
    return {"status": "success", "lecture": data}

def _view_lab_internal(lab_name):
    """Internal helper for viewing lab"""
    path = os.path.join(LAB_DIR, f"{lab_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lab draft '{lab_name}' not found."}
    data = json.load(open(path))
    return {"status": "success", "lab": data}

def _view_quiz_internal(quiz_name):
    """Internal helper for viewing quiz"""
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}
    data = json.load(open(path))
    return {"status": "success", "quiz": data}

def _view_course_internal(course_name):
    """Internal helper for viewing course"""
    path = os.path.join(COURSE_DIR, f"{course_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": "Course does not exist."}
    data = json.load(open(path))
    return {"status": "success", "course": data}

def _edit_module_internal(module_name, updates):
    """Internal helper for editing module"""
    path = os.path.join(MODULE_DIR, f"{module_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Module '{module_name}' not found."}

    data = json.load(open(path))
    data.update(updates)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Module '{module_name}' updated."}

def _edit_lecture_internal(lecture_name, updates):
    """Internal helper for editing lecture"""
    path = os.path.join(LECTURE_DIR, f"{lecture_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lecture draft '{lecture_name}' not found."}

    data = json.load(open(path))
    data.update(updates)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Lecture draft '{lecture_name}' updated."}

def _edit_lab_internal(lab_name, updates):
    """Internal helper for editing lab"""
    path = os.path.join(LAB_DIR, f"{lab_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lab draft '{lab_name}' not found."}

    data = json.load(open(path))
    data.update(updates)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Lab draft '{lab_name}' updated."}

def _edit_quiz_internal(quiz_name, updates):
    """Internal helper for editing quiz - includes question management"""
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}

    data = json.load(open(path))

    # Handle special quiz question operations
    if "add_questions" in updates:
        if "questions" not in data:
            data["questions"] = []
        data["questions"].extend(updates["add_questions"])
        updates = {k: v for k, v in updates.items() if k != "add_questions"}

    if "remove_question_index" in updates:
        idx = updates["remove_question_index"]
        if "questions" in data and 0 <= idx < len(data["questions"]):
            data["questions"].pop(idx)
        updates = {k: v for k, v in updates.items() if k != "remove_question_index"}

    if "update_question" in updates:
        idx = updates["update_question"].get("index")
        question = updates["update_question"].get("question")
        if "questions" in data and 0 <= idx < len(data["questions"]):
            data["questions"][idx] = question
        updates = {k: v for k, v in updates.items() if k != "update_question"}

    # Apply remaining updates
    data.update(updates)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Quiz draft '{quiz_name}' updated."}

def _edit_course_internal(course_name, updates):
    """Internal helper for editing course"""
    path = os.path.join(COURSE_DIR, f"{course_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Course '{course_name}' not found."}

    data = json.load(open(path))
    data.update(updates)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Course '{course_name}' updated."}

def _publish_module_internal(module_name, course_id, params):
    """Internal helper for publishing module"""
    position = params.get("position")
    return publish_module({
        "module_name": module_name,
        "course_id": course_id,
        "position": position
    })

def _publish_lecture_internal(lecture_name, course_id):
    """Internal helper for publishing lecture"""
    return publish_lecture({
        "lecture_name": lecture_name,
        "course_id": course_id
    })

def _publish_lab_internal(lab_name, course_id):
    """Internal helper for publishing lab"""
    return publish_lab({
        "lab_name": lab_name,
        "course_id": course_id
    })

def _publish_quiz_internal(quiz_name, course_id):
    """Internal helper for publishing quiz"""
    return publish_quiz({
        "quiz_name": quiz_name,
        "course_id": course_id
    })

# ============================================================================
# MODULE FUNCTIONS (Legacy - kept for backward compatibility)
# ============================================================================

def create_module_draft(params):
    module_name = params["module_name"]
    path = os.path.join(MODULE_DIR, f"{module_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Module '{module_name}' already exists."}

    title = params.get("title") or module_name.replace("_", " ").title()
    data = {
        "title": title,
        "lectures": [],
        "labs": [],
        "quizzes": []
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Module draft '{module_name}' created."}

def batch_create_modules(params):
    modules = params.get("modules", [])
    if not modules:
        return {"status": "error", "message": "No modules provided"}
    
    results = []
    for module_spec in modules:
        module_name = module_spec.get("module_name")
        title = module_spec.get("title")
        
        if not module_name:
            results.append({"status": "error", "message": "Missing module_name"})
            continue
        
        result = create_module_draft({
            "module_name": module_name,
            "title": title
        })
        results.append({"module_name": module_name, "result": result})
    
    return {
        "status": "success",
        "total": len(modules),
        "created": len([r for r in results if r.get("result", {}).get("status") == "success"]),
        "results": results
    }

def add_materials_to_module(params):
    module_name = params["module_name"]
    path = os.path.join(MODULE_DIR, f"{module_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Module '{module_name}' not found."}

    data = json.load(open(path))

    for lecture in params.get("lectures", []):
        lecture_file = lecture.replace(".pdf", ".json")
        if lecture_file not in data["lectures"]:
            data["lectures"].append(lecture_file)

    for lab in params.get("labs", []):
        lab_file = f"{lab}.json"
        if lab_file not in data["labs"]:
            data["labs"].append(lab_file)

    for quiz in params.get("quizzes", []):
        quiz_file = f"{quiz}.json"
        if quiz_file not in data["quizzes"]:
            data["quizzes"].append(quiz_file)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Updated module '{module_name}' with new materials."}

def view_module_draft(params):
    module_name = params["module_name"]
    path = os.path.join(MODULE_DIR, f"{module_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": "Module does not exist."}
    data = json.load(open(path))
    return {"status": "success", "module": data}

# ============================================================================
# LECTURE FUNCTIONS
# ============================================================================

def create_lecture_draft(params):
    lecture_name = params["lecture_name"]
    json_name = lecture_name.replace(os.path.splitext(lecture_name)[1], ".json")
    path = os.path.join(LECTURE_DIR, json_name)

    if os.path.exists(path):
        return {"status": "error", "message": f"Lecture draft '{json_name}' already exists."}

    with open("data/canvas/templates/lecture_template.json") as f:
        draft = json.load(f)

    draft["filename"] = lecture_name

    with open(path, "w") as f:
        json.dump(draft, f, indent=2)

    return {"status": "success", "message": f"Lecture draft for '{lecture_name}' created."}

def batch_create_lecture_drafts(params):
    lectures = params.get("lectures", [])
    if not lectures:
        return {"status": "error", "message": "No lectures provided"}
    
    results = []
    for lecture_spec in lectures:
        lecture_name = lecture_spec.get("lecture_name")
        
        if not lecture_name:
            results.append({"status": "error", "message": "Missing lecture_name"})
            continue
        
        result = create_lecture_draft({"lecture_name": lecture_name})
        results.append({"lecture_name": lecture_name, "result": result})
    
    return {
        "status": "success",
        "total": len(lectures),
        "created": len([r for r in results if r.get("result", {}).get("status") == "success"]),
        "results": results
    }

def view_lecture_draft(params):
    lecture_name = params["lecture_name"]
    path = os.path.join(LECTURE_DIR, f"{lecture_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lecture draft '{lecture_name}' not found."}
    data = json.load(open(path))
    return {"status": "success", "lecture": data}

def edit_lecture_draft(params):
    lecture_name = params["lecture_name"]
    key = params["key"]
    value = params["value"]
    path = os.path.join(LECTURE_DIR, f"{lecture_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lecture draft '{lecture_name}' not found."}
    data = json.load(open(path))
    data[key] = value
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return {"status": "success", "message": f"Updated '{key}' in lecture draft '{lecture_name}'."}

# ============================================================================
# LAB FUNCTIONS
# ============================================================================

def create_lab_draft(params):
    lab_name = params["lab_name"]
    path = os.path.join(LAB_DIR, f"{lab_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Lab draft '{lab_name}' already exists."}

    with open("data/canvas/templates/lab_template.json") as f:
        draft = json.load(f)

    draft["name"] = params.get("title", lab_name)
    draft["due_at"] = params["due_at"]
    draft["file_name"] = params.get("file_name", "")
    draft["description"] = params.get("description", "")
    draft["points_possible"] = params.get("points_possible", 100)
    draft["submission_types"] = params.get("submission_types", ["online_upload"])
    draft["published"] = params.get("published", True)

    with open(path, "w") as f:
        json.dump(draft, f, indent=2)

    return {"status": "success", "message": f"Lab draft '{lab_name}' created."}

def batch_create_lab_drafts(params):
    labs = params.get("labs", [])
    if not labs:
        return {"status": "error", "message": "No labs provided"}
    
    results = []
    for lab_spec in labs:
        lab_name = lab_spec.get("lab_name")
        due_at = lab_spec.get("due_at")
        title = lab_spec.get("title")
        description = lab_spec.get("description")
        points_possible = lab_spec.get("points_possible")
        submission_types = lab_spec.get("submission_types")
        published = lab_spec.get("published")
        file_name = lab_spec.get("file_name")
        
        if not lab_name or not due_at:
            results.append({"status": "error", "message": "Missing lab_name or due_at"})
            continue
        
        result = create_lab_draft({
            "lab_name": lab_name,
            "due_at": due_at,
            "title": title,
            "description": description,
            "points_possible": points_possible,
            "submission_types": submission_types,
            "published": published,
            "file_name": file_name
        })
        results.append({"lab_name": lab_name, "result": result})
    
    return {
        "status": "success",
        "total": len(labs),
        "created": len([r for r in results if r.get("result", {}).get("status") == "success"]),
        "results": results
    }

def view_lab_draft(params):
    lab_name = params["lab_name"]
    path = os.path.join(LAB_DIR, f"{lab_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lab draft '{lab_name}' not found."}
    data = json.load(open(path))
    return {"status": "success", "lab": data}

def edit_lab_draft(params):
    lab_name = params["lab_name"]
    key = params["key"]
    value = params["value"]
    path = os.path.join(LAB_DIR, f"{lab_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Lab draft '{lab_name}' not found."}
    data = json.load(open(path))
    data[key] = value
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return {"status": "success", "message": f"Updated '{key}' in lab draft '{lab_name}'."}

# ============================================================================
# QUIZ FUNCTIONS
# ============================================================================

def create_quiz_draft(params):
    quiz_name = params["quiz_name"]
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' already exists."}

    with open("data/canvas/templates/quiz_template.json") as f:
        draft = json.load(f)

    draft["title"] = params.get("title", quiz_name.replace("_", " ").title())
    if "due_at" in params:
        draft["due_at"] = params["due_at"]
    if "quiz_type" in params:
        draft["quiz_type"] = params["quiz_type"]
    if "published" in params:
        draft["published"] = params["published"]
    if "description" in params:
        draft["description"] = params["description"]
    if "questions" in params:
        draft["questions"] = params["questions"]

    with open(path, "w") as f:
        json.dump(draft, f, indent=2)

    return {"status": "success", "message": f"Quiz draft '{quiz_name}' created."}

def batch_create_quiz_drafts(params):
    quizzes = params.get("quizzes", [])
    if not quizzes:
        return {"status": "error", "message": "No quizzes provided"}
    
    results = []
    for quiz_spec in quizzes:
        quiz_name = quiz_spec.get("quiz_name")
        title = quiz_spec.get("title")
        due_at = quiz_spec.get("due_at")
        quiz_type = quiz_spec.get("quiz_type")
        published = quiz_spec.get("published")
        description = quiz_spec.get("description")
        questions = quiz_spec.get("questions")
        
        if not quiz_name:
            results.append({"status": "error", "message": "Missing quiz_name"})
            continue
        
        result = create_quiz_draft({
            "quiz_name": quiz_name,
            "title": title,
            "due_at": due_at,
            "quiz_type": quiz_type,
            "published": published,
            "description": description,
            "questions": questions
        })
        results.append({"quiz_name": quiz_name, "result": result})
    
    return {
        "status": "success",
        "total": len(quizzes),
        "created": len([r for r in results if r.get("result", {}).get("status") == "success"]),
        "results": results
    }

def view_quiz_draft(params):
    quiz_name = params["quiz_name"]
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}
    data = json.load(open(path))
    return {"status": "success", "quiz": data}

def add_quiz_question(params):
    quiz_name = params["quiz_name"]
    question = params["question"]
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}
    
    data = json.load(open(path))
    if "questions" not in data:
        data["questions"] = []
    
    data["questions"].append(question)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    return {"status": "success", "message": f"Added question to quiz '{quiz_name}'."}

def batch_add_quiz_questions(params):
    quiz_name = params["quiz_name"]
    questions = params.get("questions", [])
    
    if not questions:
        return {"status": "error", "message": "No questions provided"}
    
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}
    
    data = json.load(open(path))
    if "questions" not in data:
        data["questions"] = []
    
    data["questions"].extend(questions)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    return {
        "status": "success", 
        "message": f"Added {len(questions)} questions to quiz '{quiz_name}'.",
        "total_questions": len(data["questions"])
    }

def remove_quiz_question(params):
    quiz_name = params["quiz_name"]
    question_index = params["question_index"]
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}
    
    data = json.load(open(path))
    if "questions" not in data or not data["questions"]:
        return {"status": "error", "message": "No questions in quiz."}
    
    if question_index < 0 or question_index >= len(data["questions"]):
        return {"status": "error", "message": f"Invalid question_index {question_index}."}
    
    removed = data["questions"].pop(question_index)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    return {"status": "success", "message": f"Removed question at index {question_index}.", "removed_question": removed}

def update_quiz_question(params):
    quiz_name = params["quiz_name"]
    question_index = params["question_index"]
    updated_question = params["updated_question"]
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}
    
    data = json.load(open(path))
    if "questions" not in data or not data["questions"]:
        return {"status": "error", "message": "No questions in quiz."}
    
    if question_index < 0 or question_index >= len(data["questions"]):
        return {"status": "error", "message": f"Invalid question_index {question_index}."}
    
    data["questions"][question_index] = updated_question
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    return {"status": "success", "message": f"Updated question at index {question_index}."}

# ============================================================================
# COURSE FUNCTIONS
# ============================================================================

def create_course_draft(params):
    course_name = params["course_name"]
    path = os.path.join(COURSE_DIR, f"{course_name}.json")
    if os.path.exists(path):
        return {"status": "error", "message": f"Course draft '{course_name}' already exists."}

    data = {
        "course_name": course_name,
        "title": params.get("title", course_name.replace("_", " ").title()),
        "modules": []
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Course draft '{course_name}' created."}

def add_modules_to_course(params):
    course_name = params["course_name"]
    path = os.path.join(COURSE_DIR, f"{course_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"Course '{course_name}' not found."}

    data = json.load(open(path))
    
    for module_name in params.get("modules", []):
        if module_name not in data["modules"]:
            data["modules"].append(module_name)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "message": f"Updated course '{course_name}' with modules."}

def view_course_draft(params):
    course_name = params["course_name"]
    path = os.path.join(COURSE_DIR, f"{course_name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": "Course does not exist."}
    data = json.load(open(path))
    return {"status": "success", "course": data}

# ============================================================================
# PUBLISHING FUNCTIONS
# ============================================================================

def publish_course(params):
    import uuid
    import subprocess
    import sys
    
    course_name = params["course_name"]
    course_id = str(params.get("course_id"))
    
    if not course_id:
        return {"status": "error", "message": "Missing required 'course_id'"}

    course_path = os.path.join(COURSE_DIR, f"{course_name}.json")
    if not os.path.exists(course_path):
        return {"status": "error", "message": f"Course '{course_name}' not found."}

    try:
        course_data = json.load(open(course_path))
    except Exception as e:
        return {"status": "error", "message": f"Failed to load course JSON: {str(e)}"}

    module_names = course_data.get("modules", [])
    if not module_names:
        return {"status": "error", "message": "No modules in course."}

    job_id = str(uuid.uuid4())
    job_file = os.path.join(BASE_PATH, "canvas_jobs.json")
    
    jobs = {}
    if os.path.exists(job_file):
        with open(job_file, 'r') as f:
            jobs = json.load(f)
    
    jobs[job_id] = {
        "course_name": course_name,
        "course_id": course_id,
        "total_modules": len(module_names),
        "completed": 0,
        "status": "in_progress",
        "modules": module_names
    }
    
    with open(job_file, 'w') as f:
        json.dump(jobs, f, indent=2)
    
    subprocess.Popen(
        [sys.executable, __file__, "_background_deploy", 
         "--params", json.dumps({
             "job_id": job_id,
             "course_id": course_id,
             "module_names": module_names,
             "job_file": job_file
         })],
        stdout=open(os.devnull, 'w'),
        stderr=open(os.devnull, 'w'),
        start_new_session=True
    )
    
    return {
        "status": "started",
        "job_id": job_id,
        "message": f"Deploying {len(module_names)} modules for {course_name}",
        "check_progress": f"Read {job_file} and look for job_id: {job_id}"
    }

def _background_deploy(params):
    """Internal function - runs as detached process"""
    job_id = params["job_id"]
    course_id = params["course_id"]
    module_names = params["module_names"]
    job_file = params["job_file"]
    
    jobs = json.load(open(job_file, 'r'))
    
    for idx, module_name in enumerate(module_names):
        publish_module({
            "module_name": module_name,
            "course_id": course_id,
            "position": idx + 1
        })
        
        jobs[job_id]["completed"] = idx + 1
        with open(job_file, 'w') as f:
            json.dump(jobs, f, indent=2)
    
    jobs[job_id]["status"] = "completed"
    with open(job_file, 'w') as f:
        json.dump(jobs, f, indent=2)
    
    return {"status": "success", "message": "Background deployment complete"}

def publish_module(params):
    module_name = params["module_name"]
    course_id = str(params.get("course_id"))
    position = params.get("position")
    
    if not course_id:
        return {"status": "error", "message": "Missing required 'course_id'"}

    module_path = os.path.join(MODULE_DIR, f"{module_name}.json")
    if not os.path.exists(module_path):
        return {"status": "error", "message": f"Module '{module_name}' not found."}

    try:
        creds = json.load(open("tools/credentials.json"))
        api_key = creds.get("CANVAS_API_KEY")
        if not api_key:
            return {"status": "error", "message": "Canvas API key not found in credentials"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to load credentials: {str(e)}"}

    base_url = "https://canvas.instructure.com"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        module = json.load(open(module_path))
    except Exception as e:
        return {"status": "error", "message": f"Failed to load module JSON: {str(e)}"}

    results = []
    module_items = []

    for lecture_file in module.get("lectures", []):
        lecture_json_path = os.path.join(LECTURE_DIR, lecture_file)
        if not os.path.exists(lecture_json_path):
            results.append({"lecture": lecture_file, "status": "JSON Not Found"})
            continue

        try:
            lecture_data = json.load(open(lecture_json_path))
            filename = lecture_data.get("filename")
            if not filename:
                results.append({"lecture": lecture_file, "status": "No filename in JSON"})
                continue

            lecture_file_path = os.path.join(LECTURE_DIR, filename)
            if not os.path.exists(lecture_file_path):
                results.append({"lecture": filename, "status": "File Missing"})
                continue

            preflight_url = f"{base_url}/api/v1/courses/{course_id}/files"
            preflight_payload = {
                "name": filename,
                "size": os.path.getsize(lecture_file_path),
                "content_type": "application/pdf",
                "parent_folder_path": "/"
            }
            
            pre_resp = requests.post(preflight_url, headers=headers, json=preflight_payload)
            if pre_resp.status_code != 200:
                results.append({
                    "lecture": filename, 
                    "status": "Preflight Failed", 
                    "code": pre_resp.status_code
                })
                continue

            upload_info = pre_resp.json()
            upload_url = upload_info.get("upload_url")
            upload_params = upload_info.get("upload_params", {})

            if not upload_url:
                results.append({"lecture": filename, "status": "No upload URL"})
                continue

            with open(lecture_file_path, "rb") as f:
                files = {"file": (filename, f)}
                upload_resp = requests.post(upload_url, data=upload_params, files=files)

            if upload_resp.status_code not in [200, 201]:
                results.append({
                    "lecture": filename, 
                    "status": "Upload Failed",
                    "code": upload_resp.status_code
                })
                continue

            try:
                file_json = upload_resp.json()
                file_id = file_json.get("id")
                if file_id:
                    results.append({"lecture": filename, "file_id": file_id, "status": "Uploaded"})
                    module_items.append({"type": "File", "content_id": file_id})
                else:
                    results.append({"lecture": filename, "status": "No file ID"})
            except json.JSONDecodeError:
                results.append({"lecture": filename, "status": "Invalid JSON"})

        except Exception as e:
            results.append({"lecture": lecture_file, "status": f"Error: {str(e)}"})

    for lab_file in module.get("labs", []):
        lab_path = os.path.join(LAB_DIR, lab_file)
        if not os.path.exists(lab_path):
            results.append({"lab": lab_file, "status": "Not Found"})
            continue

        try:
            lab_data = json.load(open(lab_path))
            assignment_payload = {"assignment": lab_data}
            
            url = f"{base_url}/api/v1/courses/{course_id}/assignments"
            resp = requests.post(url, headers=headers, json=assignment_payload)
            
            if resp.status_code not in [200, 201]:
                results.append({
                    "lab": lab_file, 
                    "status": "Creation Failed",
                    "code": resp.status_code
                })
                continue

            assignment = resp.json()
            assignment_id = assignment.get("id")
            
            if assignment_id:
                results.append({"lab": lab_file, "assignment_id": assignment_id, "status": "Created"})
                module_items.append({"type": "Assignment", "content_id": assignment_id})
            else:
                results.append({"lab": lab_file, "status": "No assignment ID"})

        except Exception as e:
            results.append({"lab": lab_file, "status": f"Error: {str(e)}"})

    for quiz_file in module.get("quizzes", []):
        quiz_path = os.path.join(QUIZ_DIR, quiz_file)
        if not os.path.exists(quiz_path):
            results.append({"quiz": quiz_file, "status": "Not Found"})
            continue

        try:
            quiz_data = json.load(open(quiz_path))
            questions = quiz_data.pop("questions", [])

            # Set points_possible based on number of questions (1 point per question)
            if "points_possible" not in quiz_data and questions:
                quiz_data["points_possible"] = len(questions)

            quiz_payload = {"quiz": quiz_data}
            url = f"{base_url}/api/v1/courses/{course_id}/quizzes"
            resp = requests.post(url, headers=headers, json=quiz_payload)
            
            if resp.status_code not in [200, 201]:
                results.append({
                    "quiz": quiz_file, 
                    "status": "Quiz Creation Failed",
                    "code": resp.status_code
                })
                continue

            quiz_response = resp.json()
            quiz_id = quiz_response.get("id")
            
            if not quiz_id:
                results.append({"quiz": quiz_file, "status": "No quiz ID"})
                continue
            
            questions_added = 0
            
            for i, question in enumerate(questions):
                question_payload = {"question": question}
                question_url = f"{base_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}/questions"
                
                question_resp = requests.post(question_url, headers=headers, json=question_payload)
                
                if question_resp.status_code in [200, 201]:
                    questions_added += 1
            
            if questions_added > 0:
                results.append({
                    "quiz": quiz_file, 
                    "quiz_id": quiz_id, 
                    "status": f"Created with {questions_added}/{len(questions)} questions"
                })
                module_items.append({"type": "Quiz", "content_id": quiz_id})
            else:
                results.append({
                    "quiz": quiz_file, 
                    "quiz_id": quiz_id,
                    "status": "Quiz created but no questions added"
                })
                module_items.append({"type": "Quiz", "content_id": quiz_id})

        except Exception as e:
            results.append({"quiz": quiz_file, "status": f"Error: {str(e)}"})

    module_title = module.get("title", module_name.replace("_", " ").title())
    module_id = None

    try:
        module_lookup_url = f"{base_url}/api/v1/courses/{course_id}/modules"
        module_lookup_resp = requests.get(module_lookup_url, headers=headers)
        
        if module_lookup_resp.status_code == 200:
            existing_modules = module_lookup_resp.json()
            for mod in existing_modules:
                if mod.get("name", "").strip().lower() == module_title.strip().lower():
                    module_id = mod.get("id")
                    break

        if not module_id:
            create_module_payload = {"module": {"name": module_title}}
            
            if position is not None:
                create_module_payload["module"]["position"] = position
            
            create_module_url = f"{base_url}/api/v1/courses/{course_id}/modules"
            module_resp = requests.post(create_module_url, headers=headers, json=create_module_payload)
            
            if module_resp.status_code in [200, 201]:
                module_data = module_resp.json()
                module_id = module_data.get("id")
        else:
            if position is not None:
                update_url = f"{base_url}/api/v1/courses/{course_id}/modules/{module_id}"
                update_payload = {"module": {"position": position}}
                requests.put(update_url, headers=headers, json=update_payload)

    except Exception as e:
        return {"status": "error", "message": f"Module creation failed: {str(e)}"}

    if module_id and module_items:
        for idx, item in enumerate(module_items):
            try:
                link_url = f"{base_url}/api/v1/courses/{course_id}/modules/{module_id}/items"
                item_payload = {
                    "module_item": {
                        "type": item["type"],
                        "content_id": item["content_id"],
                        "position": idx + 1
                    }
                }
                requests.post(link_url, headers=headers, json=item_payload)
            except Exception:
                pass

    return {"status": "success", "module_id": module_id, "published": results}

def publish_lecture(params):
    lecture_name = params["lecture_name"]
    course_id = params["course_id"]

    json_name = lecture_name.replace(os.path.splitext(lecture_name)[1], ".json")
    json_path = os.path.join(LECTURE_DIR, json_name)
    file_path = os.path.join(LECTURE_DIR, lecture_name)

    if not os.path.exists(json_path):
        return {"status": "error", "message": f"Lecture JSON '{json_name}' not found."}
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"Lecture file '{lecture_name}' not found."}

    creds = json.load(open("tools/credentials.json"))
    api_key = creds.get("CANVAS_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://canvas.instructure.com"

    preflight_url = f"{base_url}/api/v1/courses/{course_id}/files"
    preflight_payload = {
        "name": lecture_name,
        "size": os.path.getsize(file_path),
        "content_type": "application/octet-stream",
        "parent_folder_path": "/"
    }
    pre_resp = requests.post(preflight_url, headers=headers, json=preflight_payload)
    if pre_resp.status_code != 200:
        return {"status": "error", "stage": "preflight", "code": pre_resp.status_code}

    upload_info = pre_resp.json()
    upload_url = upload_info["upload_url"]
    upload_params = upload_info["upload_params"]

    with open(file_path, "rb") as f:
        files = {"file": (lecture_name, f)}
        upload_resp = requests.post(upload_url, data=upload_params, files=files)

    return {"status": "success" if upload_resp.status_code < 300 else "error"}

def publish_lab(params):
    lab_name = params["lab_name"]
    course_id = params["course_id"]
    path = os.path.join(LAB_DIR, f"{lab_name}.json")

    if not os.path.exists(path):
        return {"status": "error", "message": f"Lab draft '{lab_name}' not found."}

    lab = json.load(open(path))
    creds = json.load(open("tools/credentials.json"))
    api_key = creds.get("CANVAS_API_KEY")
    url = f"https://canvas.instructure.com/api/v1/courses/{course_id}/assignments"
    headers = {"Authorization": f"Bearer {api_key}"}

    resp = requests.post(url, headers=headers, json={"assignment": lab})
    return {"status": "success" if resp.status_code < 300 else "error"}

def publish_quiz(params):
    quiz_name = params["quiz_name"]
    course_id = params["course_id"]
    path = os.path.join(QUIZ_DIR, f"{quiz_name}.json")

    if not os.path.exists(path):
        return {"status": "error", "message": f"Quiz draft '{quiz_name}' not found."}

    quiz = json.load(open(path))

    # Calculate total points based on questions (1 point per question by default)
    questions = quiz.get("questions", [])
    if questions and "points_possible" not in quiz:
        quiz["points_possible"] = len(questions)

    creds = json.load(open("tools/credentials.json"))
    api_key = creds.get("CANVAS_API_KEY")
    url = f"https://canvas.instructure.com/api/v1/courses/{course_id}/quizzes"
    headers = {"Authorization": f"Bearer {api_key}"}

    resp = requests.post(url, headers=headers, json={"quiz": quiz})
    return {"status": "success" if resp.status_code < 300 else "error"}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--params")
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}

    # New unified actions
    if args.action == "create_draft":
        result = create_draft(params)
    elif args.action == "view_draft":
        result = view_draft(params)
    elif args.action == "edit_draft":
        result = edit_draft(params)
    elif args.action == "publish":
        result = publish(params)
    # Legacy actions for backward compatibility
    elif args.action == "create_module_draft":
        result = create_module_draft(params)
    elif args.action == "batch_create_modules":
        result = batch_create_modules(params)
    elif args.action == "add_materials_to_module":
        result = add_materials_to_module(params)
    elif args.action == "view_module_draft":
        result = view_module_draft(params)
    elif args.action == "create_lecture_draft":
        result = create_lecture_draft(params)
    elif args.action == "batch_create_lecture_drafts":
        result = batch_create_lecture_drafts(params)
    elif args.action == "view_lecture_draft":
        result = view_lecture_draft(params)
    elif args.action == "edit_lecture_draft":
        result = edit_lecture_draft(params)
    elif args.action == "create_lab_draft":
        result = create_lab_draft(params)
    elif args.action == "batch_create_lab_drafts":
        result = batch_create_lab_drafts(params)
    elif args.action == "view_lab_draft":
        result = view_lab_draft(params)
    elif args.action == "edit_lab_draft":
        result = edit_lab_draft(params)
    elif args.action == "create_quiz_draft":
        result = create_quiz_draft(params)
    elif args.action == "batch_create_quiz_drafts":
        result = batch_create_quiz_drafts(params)
    elif args.action == "view_quiz_draft":
        result = view_quiz_draft(params)
    elif args.action == "add_quiz_question":
        result = add_quiz_question(params)
    elif args.action == "batch_add_quiz_questions":
        result = batch_add_quiz_questions(params)
    elif args.action == "remove_quiz_question":
        result = remove_quiz_question(params)
    elif args.action == "update_quiz_question":
        result = update_quiz_question(params)
    elif args.action == "create_course_draft":
        result = create_course_draft(params)
    elif args.action == "add_modules_to_course":
        result = add_modules_to_course(params)
    elif args.action == "view_course_draft":
        result = view_course_draft(params)
    elif args.action == "publish_course":
        result = publish_course(params)
    elif args.action == "_background_deploy":
        result = _background_deploy(params)
    elif args.action == "publish_module":
        result = publish_module(params)
    elif args.action == "publish_lecture":
        result = publish_lecture(params)
    elif args.action == "publish_lab":
        result = publish_lab(params)
    elif args.action == "publish_quiz":
        result = publish_quiz(params)
    else:
        result = {"status": "error", "message": f"Unknown action {args.action}"}

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()