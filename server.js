const express = require('express');
const { exec } = require('child_process');
const cors = require('cors');
const app = express();

app.use(cors());
app.use(express.json());

app.post('/terminal', (req, res) => {
    const { command } = req.body;
    exec(command, (error, stdout, stderr) => {
        res.json({ output: stdout || stderr || "Action effectuée." });
    });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Serveur prêt sur le port ${PORT}`));
