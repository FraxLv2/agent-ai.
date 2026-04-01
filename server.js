const express = require('express');
const { exec } = require('child_process');
const cors = require('cors');
const { GoogleGenerativeAI } = require("@google/generative-ai");

const app = express();
app.use(cors());
app.use(express.json());

// Ta clé API
const genAI = new GoogleGenerativeAI("AIzaSyCIMCDXdBQAEn60vJgloTHveo3FQ_BPw7k");

app.post('/terminal', async (req, res) => {
    const { command } = req.body;

    if (command.startsWith("ai ")) {
        try {
            // Utilisation du modèle flash sans préciser de version compliquée
            const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
            const prompt = command.replace("ai ", "");
            
            const result = await model.generateContent(`Donne uniquement la commande bash pour : ${prompt}`);
            const response = await result.response;
            const text = response.text();
            
            // Nettoyage de la commande (enlève les ```bash etc)
            const finalCmd = text.replace(/```bash|```/g, "").trim();
            
            exec(finalCmd, (error, stdout, stderr) => {
                res.json({ output: `🤖 IA exécute : ${finalCmd}\n\n${stdout || stderr || "Effectué !"}` });
            });
        } catch (e) {
            res.json({ output: "Erreur IA : " + e.message });
        }
    } else {
        exec(command, (error, stdout, stderr) => {
            res.json({ output: stdout || stderr || "OK." });
        });
    }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => console.log(`Serveur prêt` ));
