module.exports = {
    apps: [
        {
            name: "agromind-n8n",
            script: "C:\\Users\\KIIT\\AppData\\Roaming\\npm\\n8n.cmd",
            interpreter: "none",
            env: {
                N8N_PORT: "5678",
                N8N_BASIC_AUTH_ACTIVE: "false",
                WEBHOOK_URL: "http://localhost:5678"
            }
        },
        {
            name: "agromind-backend",
            cwd: "C:\\MyFiles\\AgroMindAI\\backend",
            script: "C:\\MyFiles\\AgroMindAI\\backend\\venv\\Scripts\\python.exe",
            args: "-m uvicorn main:app --host 0.0.0.0 --port 8000",
            interpreter: "none"
        },
        {
            name: "agromind-dashboard",
            cwd: "C:\\MyFiles\\AgroMindAI\\dashboard",
            script: "node_modules\\.bin\\vite.cmd",
            args: "preview --port 5173",
            interpreter: "none"
        }
    ]
}
