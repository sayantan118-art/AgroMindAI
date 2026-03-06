module.exports = {
    apps: [
        {
            name: "agromind-n8n",
            script: "n8n",
            interpreter: "none",
            env: {
                N8N_PORT: "5678",
                N8N_BASIC_AUTH_ACTIVE: "false",
                WEBHOOK_URL: "http://localhost:5678"
            }
        },
        {
            name: "agromind-backend",
            cwd: "C:\\My files\\AroMindAI\\backend",
            script: "C:\\My files\\AroMindAI\\backend\\venv\\Scripts\\uvicorn.exe",
            args: "main:app --host 0.0.0.0 --port 8000",
            interpreter: "none"
        },
        {
            name: "agromind-dashboard",
            cwd: "C:\\My files\\AroMindAI\\dashboard",
            script: "npm",
            args: "run preview -- --port 5173",
            interpreter: "none"
        }
    ]
}
