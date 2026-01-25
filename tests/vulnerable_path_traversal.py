import os
from flask import Flask, request, send_file

app = Flask(__name__)

@app.route('/download')
def download():
    filename = request.args.get('file')
    # VULNERABLE: No validation
    return send_file(filename)

@app.route('/read')
def read():
    path = request.args.get('path')
    # VULNERABLE: open with user input
    with open(path, 'r') as f:
        return f.read()

if __name__ == '__main__':
    app.run()
