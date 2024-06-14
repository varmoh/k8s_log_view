import subprocess
import secrets
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import datetime
from kubernetes import client, config

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Custom Jinja2 filter for formatting dates
def format_datetime(value, format='%d-%m-%Y'):
    if value is None:
        return ""
    if isinstance(value, str):
        if value == 'now':
            value = datetime.datetime.now()
        else:
            value = datetime.datetime.fromisoformat(value)
    return value.strftime(format)

app.jinja_env.filters['datetime'] = format_datetime

def get_namespaces():
    v1 = client.CoreV1Api()
    namespaces = v1.list_namespace()
    return [ns.metadata.name for ns in namespaces.items]

def get_pods(namespace):
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace)
    return [pod.metadata.name for pod in pods.items]

def is_log_line(line):
    return not (line.startswith("total ") or 
                line.startswith("drwx") or 
                line.startswith("PWD=") or 
                line.startswith("SHLVL=") or 
                line.startswith("-") or
                line.startswith("_=/"))

def get_pod_logs(namespace, pod_name, lines=100, grep=None):
    result = subprocess.run(["kubectl", "logs", "--tail", str(lines), pod_name, "-n", namespace], capture_output=True, text=True)
    logs = result.stdout.splitlines()
    filtered_logs = [line for line in logs if is_log_line(line)]
    if grep:
        filtered_logs = [line for line in filtered_logs if grep in line]
    return filtered_logs

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        namespace = request.form['namespace']
        pod_name = request.form['pod_name']
        grep = request.form.get('grep', '')
        lines = request.form.get('lines', 100)  # Ensure lines is correctly captured from form
        return redirect(url_for('logs', namespace=namespace, pod_name=pod_name, grep=grep, lines=lines))
    else:
        try:
            config.load_kube_config()
            namespaces = get_namespaces()
            selected_namespace = request.args.get('namespace', namespaces[0] if namespaces else None)
            pods = get_pods(selected_namespace) if selected_namespace else []
            return render_template('index.html', namespaces=namespaces, selected_namespace=selected_namespace, pods=pods)
        except Exception as e:
            flash(str(e))
            return render_template('index.html', namespaces=[], selected_namespace=None, pods=[])
    
@app.route('/get_pods', methods=['POST'])
def get_pods_for_namespace():
    try:
        namespace = request.form['namespace']
        config.load_kube_config()
        pods = get_pods(namespace)
        return jsonify(pods)
    except Exception as e:
        return jsonify(error=str(e))

@app.route('/logs/<namespace>/<pod_name>', methods=['GET'])
def logs(namespace, pod_name):
    lines = request.args.get('lines', default=100, type=int)
    grep = request.args.get('grep', default='', type=str)
    logs = get_pod_logs(namespace, pod_name, lines, grep)
    return render_template('logs.html', pod_name=pod_name, logs=logs, grep=grep)

if __name__ == '__main__':
    app.run(debug=True)
