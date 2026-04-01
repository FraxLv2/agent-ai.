const express = require('express');
const { exec } = require('child_process');
const cors = require('cors');
const { GoogleGenerativeAI } = require("@google/generative-ai");

const app = express();
app.use(cors());
app.use(express.json());

// Utilise la variable sécurisée de Railway
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

app.post('/terminal', async (req, res) => {
    const { command } = req.body;

    if (command.startsWith("ai ")) {
        try {
            // On utilise le nom le plus simple, c'est celui qui fonctionne le mieux actuellement
            const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
            const prompt = command.replace("ai ", "");
            
            const result = await model.generateContent(`Donne UNIQUEMENT la commande bash pour : ${prompt}. Pas de blabla.`);
            const response = await result.response;
            const text = response.text();
            
            const finalCmd = text.replace(/```bash|```/g, "").trim();
            
            exec(finalCmd, (error, stdout, stderr) => {
                res.json({ output: `🤖 IA exécute : ${finalCmd}\n\n${stdout || stderr || "Effectué !"}` });
            });
        } catch (e) {
            res.json({ output: "Erreur IA : " + e.message + " | Vérifie que ta clé API est bien active dans Railway." });
        }
    } else {
        exec(command, (error, stdout, stderr) => {
            res.json({ output: stdout || stderr || "OK." });
        });
    }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => console.log(`Serveur opérationnel`));
