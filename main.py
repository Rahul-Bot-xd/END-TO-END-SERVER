Suraj Kumar:
import requests
import random
import string
import time
import os
from threading import Thread, Event
from flask import Flask, render_template, request, jsonify, send_file
import json
from datetime import datetime

app = Flask(name)

# Global dictionary to store tasks
tasks = {}

# Headers for Facebook API
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://www.facebook.com',
    'Referer': 'https://www.facebook.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}

def generate_task_id():
    """Generate 10-letter random task ID"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def load_tokens(token_input):
    """Load tokens from either single token or file"""
    if os.path.isfile(token_input):
        with open(token_input, 'r') as f:
            tokens = [line.strip() for line in f if line.strip()]
        return tokens, 'file'
    else:
        return [token_input], 'single'

def load_messages(message_file):
    """Load messages from file"""
    if os.path.isfile(message_file):
        with open(message_file, 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        return messages
    return []

def send_messages_strong(task_id, access_tokens, thread_id, hatersname, lastname, time_interval, messages):
    """Modified function to send messages with task management"""
    stop_event = tasks[task_id]['stop_event']
    token_type = tasks[task_id]['token_type']
    
    while not stop_event.is_set() and tasks[task_id]['status'] != 'stopped':
        for message in messages:
            if stop_event.is_set() or tasks[task_id]['status'] == 'stopped':
                break
                
            formatted_message = f"{hatersname} {message} {lastname}"
            
            for access_token in access_tokens:
                if stop_event.is_set() or tasks[task_id]['status'] == 'stopped':
                    break
                
                api_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
                
                parameters = {
                    'access_token': access_token, 
                    'message': formatted_message
                }
                
                try:
                    response = requests.post(
                        api_url, 
                        data=parameters, 
                        headers=headers,
                        timeout=30
                    )
                    
                    # Update last message
                    tasks[task_id]['last_message'] = formatted_message
                    tasks[task_id]['sent_count'] += 1
                    
                except Exception as e:
                    tasks[task_id]['last_message'] = f"Error: {str(e)}"
                
                # Wait for time interval between messages
                time.sleep(time_interval)
        
        # Wait 10 seconds before next circle if not stopped
        if not stop_event.is_set() and tasks[task_id]['status'] != 'stopped':
            time.sleep(10)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_task', methods=['POST'])
def start_task():
    try:
        # Get form data
        token_input = request.form['token_input']
        hatersname = request.form['hatersname']

lastname = request.form['lastname']
        convo_id = request.form['convo_id']
        time_interval = max(40, int(request.form['time_interval']))  # Minimum 40 seconds
        message_file = request.files['message_file']
        
        # Save message file
        message_filename = f"messages_{int(time.time())}.txt"
        message_file.save(message_filename)
        
        # Load tokens and messages
        access_tokens, token_type = load_tokens(token_input)
        messages = load_messages(message_filename)
        
        if not access_tokens:
            return jsonify({'error': 'No valid tokens found'})
        
        if not messages:
            return jsonify({'error': 'No messages found in file'})
        
        # Generate task ID
        task_id = generate_task_id()
        
        # Create task entry
        stop_event = Event()
        tasks[task_id] = {
            'stop_event': stop_event,
            'status': 'running',
            'hatersname': hatersname,
            'lastname': lastname,
            'convo_id': convo_id,
            'time_interval': time_interval,
            'messages': messages,
            'access_tokens': access_tokens,
            'token_type': token_type,
            'last_message': 'No messages sent yet',
            'sent_count': 0,
            'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'thread': None
        }
        
        # Start the thread
        thread = Thread(
            target=send_messages_strong,
            args=(task_id, access_tokens, convo_id, hatersname, lastname, time_interval, messages)
        )
        thread.daemon = True
        thread.start()
        
        tasks[task_id]['thread'] = thread
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Your nonstop server has been started successfully!'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/task_status', methods=['POST'])
def task_status():
    task_id = request.form['task_id']
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    
    task = tasks[task_id]
    return jsonify({
        'status': task['status'],
        'last_message': task['last_message'],
        'sent_count': task['sent_count'],
        'start_time': task['start_time']
    })

@app.route('/stop_task', methods=['POST'])
def stop_task():
    task_id = request.form['task_id']
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    
    tasks[task_id]['stop_event'].set()
    tasks[task_id]['status'] = 'stopped'
    
    return jsonify({'success': True, 'message': 'Task stopped successfully'})

@app.route('/resume_task', methods=['POST'])
def resume_task():
    task_id = request.form['task_id']
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    
    tasks[task_id]['stop_event'].clear()
    tasks[task_id]['status'] = 'running'
    
    # Restart the thread
    task = tasks[task_id]
    thread = Thread(
        target=send_messages_strong,
        args=(task_id, task['access_tokens'], task['convo_id'], 
              task['hatersname'], task['lastname'], task['time_interval'], 
              task['messages'])
    )
    thread.daemon = True
    thread.start()
    tasks[task_id]['thread'] = thread
    
    return jsonify({'success': True, 'message': 'Task resumed successfully'})

@app.route('/delete_task', methods=['POST'])
def delete_task():
    task_id = request.form['task_id']
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    
    tasks[task_id]['stop_event'].set()
    del tasks[task_id]
    
    return jsonify({'success': True, 'message': 'Task deleted successfully'})

# HTML Template
@app.route('/template')
def template():
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAHUL SINGH CONVO SERVER</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.9);
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            border: 2px solid #e0e0e0;
        }
        
        .owner-info {
            font-weight: bold;
            color: #333;
            font-size: 16px;
        }
        
        .title {
            text-align: center;
            font-size: 2.5em;
            font-weight: bold;
            background: linear-gradient(45deg, #ff0000, #ff6b6b, #ee5a24);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            animation: shine 2s infinite;
        }
        
        @keyframes shine {
            0% { opacity: 0.8; }
            50% { opacity: 1; }
            100% { opacity: 0.8; }
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
            font-size: 16px;
        }
        
        input, textarea, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #ff6b6b;
        }
        
        .btn {
            background: linear-gradient(45deg, #ff6b6b, #ee5a24);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
            width: 100%;
            margin-top: 10px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .btn-copy {
            background: linear-gradient(45deg, #4ecdc4, #44a08d);
            padding: 10px 20px;
            font-size: 14px;
            width: auto;
        }
        
        .task-controls {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .btn-stop { background: linear-gradient(45deg, #ff6b6b, #c23616); }
        .btn-resume { background: linear-gradient(45deg, #4cd137, #44bd32); }
        .btn-delete { background: linear-gradient(45deg, #e84118, #c23616); }
        .btn-status { background: linear-gradient(45deg, #00a8ff, #0097e6); }
        
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;

background: #f8f9fa;
            border-left: 4px solid #007bff;
        }
        
        .status-info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 10px;
            margin-top: 10px;
        }
        
        .copy-section {
            display: flex;
            gap: 10px;
            align-items: center;
            margin: 15px 0;
        }
        
        .task-id {
            font-family: monospace;
            background: #f1f3f4;
            padding: 10px;
            border-radius: 5px;
            flex-grow: 1;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="owner-info">OWNER RAHUL SINGH</div>
        <div class="title">RAHUL SINGH CONVO SERVER</div>
        <div class="owner-info">DEVELOPED BY RAHUL SINGH</div>
    </div>
    
    <div class="container">
        <form id="taskForm" enctype="multipart/form-data">
            <div class="form-group">
                <label for="token_input">Access Token (Single token or upload token file):</label>
                <input type="text" id="token_input" name="token_input" placeholder="Enter single token or path to token file" required>
            </div>
            
            <div class="form-group">
                <label for="hatersname">Haters Name:</label>
                <input type="text" id="hatersname" name="hatersname" placeholder="Enter haters name" required>
            </div>
            
            <div class="form-group">
                <label for="lastname">Last Name:</label>
                <input type="text" id="lastname" name="lastname" placeholder="Enter last name" required>
            </div>
            
            <div class="form-group">
                <label for="convo_id">Conversation ID:</label>
                <input type="text" id="convo_id" name="convo_id" placeholder="Enter conversation ID" required>
            </div>
            
            <div class="form-group">
                <label for="time_interval">Time Interval (seconds - minimum 40):</label>
                <input type="number" id="time_interval" name="time_interval" value="40" min="40" required>
            </div>
            
            <div class="form-group">
                <label for="message_file">Message File:</label>
                <input type="file" id="message_file" name="message_file" accept=".txt" required>
            </div>
            
            <button type="submit" class="btn">START NONSTOP SERVER</button>
        </form>
        
        <div id="taskResult" style="display: none;"></div>
        
        <div class="task-controls" style="display: none;" id="taskControls">
            <input type="text" id="statusTaskId" placeholder="Enter your Task ID">
            <button class="btn btn-status" onclick="checkStatus()">Check Status</button>
            <button class="btn btn-stop" onclick="stopTask()">Stop Task</button>
            <button class="btn btn-resume" onclick="resumeTask()">Resume Task</button>
            <button class="btn btn-delete" onclick="deleteTask()">Delete Task</button>
        </div>
        
        <div id="statusResult"></div>
    </div>

    <script>
        document.getElementById('taskForm').addEventListener('submit', function(e) {
            e.preventDefault();
            startTask();
        });
        
        function startTask() {
            const formData = new FormData(document.getElementById('taskForm'));
            
            fetch('/start_task', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                const resultDiv = document.getElementById('taskResult');
                if (data.success) {

resultDiv.innerHTML = 
                        <div class="result" style="border-left-color: #4caf50;">
                            <h3>✅ ${data.message}</h3>
                            <div class="copy-section">
                                <div class="task-id">${data.task_id}</div>
                                <button class="btn btn-copy" onclick="copyToClipboard('${data.task_id}')">Copy Task ID</button>
                            </div>
                            <p><strong>Save this Task ID to manage your task later!</strong></p>
                        </div>
                    ;
                    document.getElementById('taskControls').style.display = 'flex';
                } else {
                    resultDiv.innerHTML = 
                        <div class="result" style="border-left-color: #f44336;">
                            <h3>❌ Error: ${data.error}</h3>
                        </div>
                    ;
                }
                resultDiv.style.display = 'block';
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                alert('Task ID copied to clipboard!');
            });
        }
        
        function checkStatus() {
            const taskId = document.getElementById('statusTaskId').value;
            if (!taskId) {
                alert('Please enter Task ID');
                return;
            }
            
            const formData = new FormData();
            formData.append('task_id', taskId);
            
            fetch('/task_status', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                const statusDiv = document.getElementById('statusResult');
                if (data.error) {
                    statusDiv.innerHTML = 
                        <div class="result" style="border-left-color: #f44336;">
                            <h3>❌ ${data.error}</h3>
                        </div>
                    ;
                } else {
                    statusDiv.innerHTML = 
                        <div class="status-info">
                            <h3>📊 Task Status: ${data.status.toUpperCase()}</h3>
                            <p><strong>Last Message:</strong> ${data.last_message}</p>
                            <p><strong>Messages Sent:</strong> ${data.sent_count}</p>
                            <p><strong>Start Time:</strong> ${data.start_time}</p>
                        </div>
                    ;
                }
            });
        }
        
        function stopTask() {
            const taskId = document.getElementById('statusTaskId').value;
            if (!taskId) {
                alert('Please enter Task ID');
                return;
            }
            
            const formData = new FormData();
            formData.append('task_id', taskId);
            
            fetch('/stop_task', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                checkStatus();
            });
        }
        
        function resumeTask() {
            const taskId = document.getElementById('statusTaskId').value;
            if (!taskId) {
                alert('Please enter Task ID');
                return;
            }
            
            const formData = new FormData();
            formData.append('task_id', taskId);
            
            fetch('/resume_task', {
                method: 'POST',

body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                checkStatus();
            });
        }
        
        function deleteTask() {
            const taskId = document.getElementById('statusTaskId').value;
            if (!taskId) {
                alert('Please enter Task ID');
                return;
            }
            
            const formData = new FormData();
            formData.append('task_id', taskId);
            
            fetch('/delete_task', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                document.getElementById('statusResult').innerHTML = '';
                document.getElementById('statusTaskId').value = '';
            });
        }
    </script>
</body>
</html>
'''

if name == 'main':
    print("🚀 RAHUL SINGH CONVO SERVER STARTING...")
    print("📍 Debug Mode: OFF")
    print("📍 Port: 5000")
    print("📍 Access at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
