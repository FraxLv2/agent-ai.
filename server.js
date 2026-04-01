const express = require('express');
const { exec } = require('child_process');
const cors = require('cors');
const { GoogleGenerativeAI } = require("@google/generative-ai");

const app = express();
app.use(cors());
app.use(express.json());

// Ta clé est configurée ici
const genAI = new GoogleGenerativeAI("AIzaSyCIMCDXdBQAEn60vJgloTHveo3FQ_BPw7k");

app.post('/terminal', async (req, res) => {
    const { command } = req.body;

    // Commande IA : commence par "ai "
    if (command.startsWith("ai ")) {
        const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
        const prompt = command.replace("ai ", "");
        
        try {
            const result = await model.generateContent(`Tu es un agent expert Linux. L'utilisateur veut : ${prompt}. 
            Donne UNIQUEMENT la commande bash, sans texte autour, sans bloc de code.`);
            const response = await result.response;
            const finalCmd = response.text().trim().replace(/```bash|```/g, ""); // Nettoyage au cas où
            
            exec(finalCmd, (error, stdout, stderr) => {
                res.json({ output: `🤖 IA exécute : ${finalCmd}\n\nRésultat :\n${stdout || stderr || "Terminé avec succès."}` });
            });
        } catch (e) {
            res.json({ output: "Erreur IA : " + e.message });
        }
    } else {
        // Commande manuelle
        exec(command, (error, stdout, stderr) => {
            res.json({ output: stdout || stderr || "Action effectuée." });
        });
    }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => console.log(`Serveur actif sur port ${PORT}`));
