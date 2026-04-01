const express = require('express');
const { exec } = require('child_process');
const cors = require('cors');
const { GoogleGenerativeAI } = require("@google/generative-ai");

const app = express();
app.use(cors());
app.use(express.json());

// On initialise l'IA avec la clé de Railway
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

app.post('/terminal', async (req, res) => {
    const { command } = req.body;

    if (command.startsWith("ai ")) {
        try {
            // FORCE LE MODÈLE SANS 'v1beta'
            const model = genAI.getGenerativeModel({ 
                model: "gemini-1.5-flash",
                apiVersion: 'v1' // On force la version stable
            });
            
            const prompt = command.replace("ai ", "");
            
            const result = await model.generateContent(`Donne uniquement la commande bash pour : ${prompt}. Pas de texte.`);
            const response = await result.response;
            const text = response.text();
            
            const finalCmd = text.replace(/```bash|```|`/g, "").trim();
            
            exec(finalCmd, (error, stdout, stderr) => {
                res.json({ output: `🤖 IA exécute : ${finalCmd}\n\n${stdout || stderr || "Succès !"}` });
            });
        } catch (e) {
            // Si ça échoue encore, on affiche un message très clair
            res.json({ output: "Erreur IA : " + e.message + "\n\n💡 Conseil : Vérifie que ta clé API dans Railway est bien la NOUVELLE clé que tu as créée." });
        }
    } else {
        exec(command, (error, stdout, stderr) => {
            res.json({ output: stdout || stderr || "OK." });
        });
    }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => console.log(`Serveur prêt`));
