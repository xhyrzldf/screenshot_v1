import os
import json
from mitmproxy import http
from datetime import datetime
import logging

# 设置日志级别
LOG_LEVEL = logging.ERROR  # 可以根据需要改为 DEBUG, INFO, WARNING, ERROR, CRITICAL

# 获取用户数据路径的函数
def get_user_data_path(relative_path):
    user_data_dir = os.path.expanduser('~/.auto-test-recorder')
    return os.path.join(user_data_dir, relative_path)


logging.basicConfig(level=LOG_LEVEL,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename=get_user_data_path("mitmproxy_log.txt"),
                    filemode='a')

# 替换原来的 log_to_file 函数
def log_to_file(message, level=logging.INFO):
    if level >= LOG_LEVEL:
        logging.log(level, message)

def get_current_test_case():
    try:
        current_test_case_path = get_user_data_path("current_test_case.json")
        with open(current_test_case_path, "r") as file:
            current_test_case = json.load(file)
            return current_test_case["module_id"], current_test_case["case_id"]
    except Exception as e:
        log_to_file(f"Error reading current test case: {str(e)}")
        return None, None


def response(flow: http.HTTPFlow) -> None:
    try:
        content_type = flow.response.headers.get("Content-Type", "")

        if any(ct in content_type for ct in ["application/json", "text/html", "text/plain", "application/xml"]):
            error = {
                "url": flow.request.pretty_url,
                "header": [f"{name}:{value}" for name, value in flow.request.headers.items()],
                "method": flow.request.method,
                "data": flow.request.query or flow.request.text,
                "result": flow.response.text[:1000],
                "status": flow.response.status_code,
                "isSuccess": flow.response.status_code == 200,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            update_error_json_with_error_data(error)
    except Exception as e:
        log_to_file(f"Error in response function: {str(e)}")


def update_error_json_with_error_data(error):
    try:
        import_file_path = get_user_data_path("import.json")

        if not os.path.exists(import_file_path):
            log_to_file(f"import.json file does not exist at {import_file_path}", logging.ERROR)
            return

        with open(import_file_path, "r") as file:
            data = json.load(file)

        current_module_id, current_case_id = get_current_test_case()

        if current_module_id and current_case_id:
            for module in data:
                if str(module["id"]) == current_module_id:
                    for case in module.get("caseVoList", []):
                        if str(case["id"]) == current_case_id:
                            existing_errors = case.get("httpResult", [])
                            if isinstance(existing_errors, str):
                                try:
                                    existing_errors = json.loads(existing_errors)
                                except json.JSONDecodeError:
                                    existing_errors = []

                            if not isinstance(existing_errors, list):
                                existing_errors = [existing_errors] if existing_errors else []

                            existing_errors.append(error)
                            case["httpResult"] = json.dumps(existing_errors, ensure_ascii=False)

                            with open(import_file_path, "w") as file:
                                json.dump(data, file, ensure_ascii=False, indent=4)

                            log_to_file(f"Successfully updated httpResult for case {current_case_id}")
                            return

            log_to_file(f"Could not find case {current_case_id} in module {current_module_id}")
        else:
            log_to_file("Current test case information not found", logging.ERROR)
    except Exception as e:
        log_to_file(f"Error updating error json: {str(e)}", logging.ERROR)