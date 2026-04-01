const express = require('express');
const { exec } = require('child_process');
const cors = require('cors');
const { GoogleGenerativeAI } = require("@google/generative-ai");

const app = express();
app.use(cors());
app.use(express.json());

// Utilise la clé API cachée dans Railway
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

app.post('/terminal', async (req, res) => {
    const { command } = req.body;

    if (command.startsWith("ai ")) {
        try {
            // ON CHANGE ICI : gemini-pro est le plus compatible
            const model = genAI.getGenerativeModel({ model: "gemini-pro" });
            const prompt = command.replace("ai ", "");
            
            const result = await model.generateContent(`Donne UNIQUEMENT la commande linux bash pour : ${prompt}. Pas de texte, pas de blabla.`);
            const response = await result.response;
            const text = response.text();
            
            // Nettoyage des caractères bizarres
            const finalCmd = text.replace(/```bash|```|`/g, "").trim();
            
            exec(finalCmd, (error, stdout, stderr) => {
                res.json({ output: `🤖 IA exécute : ${finalCmd}\n\n${stdout || stderr || "Opération réussie !"}` });
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
app.listen(PORT, () => console.log(`Prêt !`));
