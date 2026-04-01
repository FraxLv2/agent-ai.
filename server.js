const express = require('express');
const { exec } = require('child_process');
const cors = require('cors');
const { GoogleGenerativeAI } = require("@google/generative-ai");

const app = express();
app.use(cors());
app.use(express.json());

// 🔐 clé API sécurisée (NE PAS mettre en dur)
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

app.post('/terminal', async (req, res) => {
    const { command } = req.body;

    if (command.startsWith("ai ")) {
        try {
            const model = genAI.getGenerativeModel({
                model: "gemini-1.5-flash-latest" // ✅ modèle corrigé
            });

            const prompt = command.replace("ai ", "");

            const result = await model.generateContent(
                `Donne uniquement une commande bash simple et SÉCURISÉE pour : ${prompt}`
            );

            const text = result.response.text();
            const finalCmd = text.replace(/```bash|```/g, "").trim();

            // 🔒 sécurité minimale
            const forbidden = ["rm", "shutdown", "reboot", "mkfs", "dd"];
            if (forbidden.some(cmd => finalCmd.includes(cmd))) {
                return res.json({ output: "❌ Commande refusée (sécurité)" });
            }

            exec(finalCmd, (error, stdout, stderr) => {
                res.json({
                    output: `🤖 IA exécute : ${finalCmd}\n\n${stdout || stderr || "Effectué !"}`
                });
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
app.listen(PORT, () => console.log(`Serveur prêt sur ${PORT}`));
