from flask import Flask, request, jsonify
from flask_cors import CORS
import docker
import tempfile
import os
import uuid

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Docker client
docker_client = docker.from_env()

# Language configurations
LANGUAGE_CONFIGS = {
    'python': {
        'image': 'python:3.9-slim',
        'extension': '.py',
        'command': 'python /tmp/code.py',
        'timeout': 15
    },
    'javascript': {
        'image': 'node:16-slim',
        'extension': '.js',
        'command': 'node /tmp/code.js',
        'timeout': 15
    },
    'js': {
        'image': 'node:16-slim',
        'extension': '.js',
        'command': 'node /tmp/code.js',
        'timeout': 15
    },
    'java': {
        'image': 'openjdk:11-slim',
        'extension': '.java',
        'command': 'bash -c "cd /tmp && javac Code.java && java Code"',
        'filename': 'Code.java',
        'timeout': 20
    },
    'cpp': {
        'image': 'gcc:latest',
        'extension': '.cpp',
        'command': 'bash -c "g++ /tmp/code.cpp -o /tmp/app && /tmp/app"',
        'timeout': 20
    },
    'c': {
        'image': 'gcc:latest',
        'extension': '.c',
        'command': 'bash -c "gcc /tmp/code.c -o /tmp/app && /tmp/app"',
        'timeout': 20
    },
    'csharp': {
        'image': 'mcr.microsoft.com/dotnet/sdk:6.0',
        'extension': '.cs',
        'command': 'bash -c "cd /tmp && dotnet new console -n app && mv /tmp/code.cs app/Program.cs && cd app && dotnet run"',
        'filename': 'code.cs',
        'timeout': 30
    },
    'go': {
        'image': 'golang:1.19-alpine',
        'extension': '.go',
        'command': 'go run /tmp/code.go',
        'timeout': 20
    },
    'rust': {
        'image': 'rust:1.70-slim',
        'extension': '.rs',
        'command': 'bash -c "rustc /tmp/code.rs -o /tmp/app && /tmp/app"',
        'timeout': 30
    },
    'ruby': {
        'image': 'ruby:3.2-slim',
        'extension': '.rb',
        'command': 'ruby /tmp/code.rb',
        'timeout': 15
    },
    'php': {
        'image': 'php:8.2-cli',
        'extension': '.php',
        'command': 'php /tmp/code.php',
        'timeout': 15
    },
    'perl': {
        'image': 'perl:5.36-slim',
        'extension': '.pl',
        'command': 'perl /tmp/code.pl',
        'timeout': 15
    },
    'bash': {
        'image': 'alpine:latest',
        'extension': '.sh',
        'command': 'sh /tmp/code.sh',
        'timeout': 10
    },
    'html': {
        'image': 'nginx:alpine',
        'extension': '.html',
        'command': 'cat /tmp/code.html',
        'type': 'html',
        'timeout': 5
    },
    'css': {
        'image': 'alpine:latest',
        'extension': '.css',
        'command': 'cat /tmp/code.css',
        'type': 'text',
        'timeout': 5
    },
    'sql': {
        'image': 'sqlite:latest',
        'extension': '.sql',
        'command': 'sqlite3 :memory: < /tmp/code.sql',
        'timeout': 15
    },
    'r': {
        'image': 'r-base:latest',
        'extension': '.r',
        'command': 'Rscript /tmp/code.r',
        'timeout': 20
    },
    'swift': {
        'image': 'swift:5.7',
        'extension': '.swift',
        'command': 'swift /tmp/code.swift',
        'timeout': 25
    },
    'kotlin': {
        'image': 'kotlin:latest',
        'extension': '.kt',
        'command': 'bash -c "kotlinc /tmp/code.kt -include-runtime -d /tmp/app.jar && java -jar /tmp/app.jar"',
        'timeout': 25
    },
    'scala': {
        'image': 'hseeberger/scala-sbt:11.0.14_1.6.2_2.13.8',
        'extension': '.scala',
        'command': 'scala /tmp/code.scala',
        'timeout': 25
    },
    'typescript': {
        'image': 'node:16-slim',
        'extension': '.ts',
        'command': 'bash -c "npm install -g ts-node typescript && ts-node /tmp/code.ts"',
        'timeout': 25
    },
    'dart': {
        'image': 'google/dart:latest',
        'extension': '.dart',
        'command': 'dart /tmp/code.dart',
        'timeout': 20
    }
}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'supported_languages': list(LANGUAGE_CONFIGS.keys())
    })

@app.route('/run-code', methods=['POST'])
def run_code():
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python').lower()
    
    # Check if language is supported
    if language not in LANGUAGE_CONFIGS:
        return jsonify({
            'output': f'Language "{language}" not supported. Supported languages: {", ".join(LANGUAGE_CONFIGS.keys())}',
            'error': True
        })
    
    config = LANGUAGE_CONFIGS[language]
    execution_id = str(uuid.uuid4())[:8]
    
    try:
        # For HTML/CSS, just return the code for browser rendering
        if language in ['html', 'css']:
            return jsonify({
                'output': code,
                'error': False,
                'type': config.get('type', 'text')
            })
        
        # Execute in Docker
        result = execute_in_docker(code, config, language, execution_id)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'output': str(e), 'error': True})

def execute_in_docker(code, config, language, execution_id):
    temp_file = None
    container = None
    
    try:
        # Determine filename
        filename = config.get('filename', f'code{config["extension"]}')
        
        # Create temporary file with code
        with tempfile.NamedTemporaryFile(mode='w', suffix=config['extension'], delete=False) as f:
            # Special handling for Java
            if language == 'java':
                # Replace class name with Code if it's the main class
                import re
                # Find public class name
                class_match = re.search(r'public\s+class\s+(\w+)', code)
                if class_match and class_match.group(1) != 'Code':
                    code = code.replace(f'public class {class_match.group(1)}', 'public class Code')
                f.write(code)
            # Special handling for C# to ensure proper namespace
            elif language == 'csharp':
                if 'namespace' not in code:
                    code = 'using System;\n\n' + code
                f.write(code)
            else:
                f.write(code)
            temp_file = f.name
        
        # Prepare volume mount
        volumes = {temp_file: {'bind': f'/tmp/{filename}', 'mode': 'ro'}}
        
        # Run container
        container = docker_client.containers.run(
            image=config['image'],
            command=config['command'],
            volumes=volumes,
            mem_limit='256m',
            nano_cpus=500000000,  # 0.5 CPU
            network_disabled=True,  # Disable network for security
            detach=True,
            remove=False,
            stdout=True,
            stderr=True
        )
        
        # Wait for container with timeout
        try:
            result = container.wait(timeout=config['timeout'])
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
            
            # Check exit code
            if result['StatusCode'] != 0:
                return {'output': logs, 'error': True}
            
            return {'output': logs, 'error': False}
            
        except docker.errors.APIError as e:
            if 'Timeout' in str(e):
                container.kill()
                return {'output': f'Execution timeout ({config["timeout"]} seconds)', 'error': True}
            raise
            
        finally:
            # Clean up container
            try:
                container.remove()
            except:
                pass
            
    except docker.errors.ContainerError as e:
        return {'output': e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e), 'error': True}
    except Exception as e:
        return {'output': str(e), 'error': True}
    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass

@app.route('/list-languages', methods=['GET'])
def list_languages():
    return jsonify({
        'languages': list(LANGUAGE_CONFIGS.keys())
    })

@app.route('/pull-images', methods=['POST'])
def pull_images():
    """Pull all required Docker images (run once)"""
    results = {}
    for lang, config in LANGUAGE_CONFIGS.items():
        if 'image' in config:
            try:
                print(f"Pulling {config['image']}...")
                docker_client.images.pull(config['image'])
                results[lang] = 'success'
                print(f"âœ… Pulled {config['image']}")
            except Exception as e:
                results[lang] = str(e)
                print(f"âŒ Failed to pull {config['image']}: {e}")
    
    return jsonify(results)

@app.route('/check-images', methods=['GET'])
def check_images():
    """Check which Docker images are already pulled"""
    results = {}
    for lang, config in LANGUAGE_CONFIGS.items():
        if 'image' in config:
            try:
                docker_client.images.get(config['image'])
                results[lang] = 'available'
            except:
                results[lang] = 'missing'
    
    return jsonify(results)

if __name__ == '__main__':
    print("ðŸš€ Starting Code Runner API...")
    print(f"ðŸ“š Supported languages: {len(LANGUAGE_CONFIGS)}")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)