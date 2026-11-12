Config = {}

-- Commande de test : /sortirvoiture [modele]   (mettre false pour la desactiver)
Config.Command        = 'sortirvoiture'
Config.DefaultModel   = 'adder'
Config.SpawnDistance  = 7.0      -- distance devant le joueur pour la commande
Config.WarpIntoVehicle = true    -- mettre le joueur dans la voiture a la fin
Config.Cooldown       = 8        -- secondes entre deux sorties (verifie cote serveur)
Config.SyncDistance   = 150.0    -- les joueurs a moins de X m voient l'animation

-- Dimensions de la trappe (en metres)
Config.Hatch = {
    width  = 3.6,   -- largeur (gauche/droite de la voiture)
    length = 6.4,   -- longueur (avant/arriere de la voiture)
    depth  = 3.5,   -- profondeur d'ou la voiture monte
}

-- Durees de l'animation (en millisecondes)
Config.Timings = {
    open  = 1600,   -- ouverture des portes
    rise  = 3200,   -- montee de la plateforme
    hold  = 600,    -- pause avant fermeture
    close = 1300,   -- fermeture des portes
}

-- Couleurs (neon futuriste)
Config.Colors = {
    neon  = { r = 0,  g = 220, b = 255 },  -- cyan
    plate = { r = 40, g = 44,  b = 52  },  -- metal sombre
    hole  = { r = 3,  g = 3,   b = 6   },  -- fond du trou
}

-- Garages : un point ou appuyer sur E, et l'endroit ou la trappe s'ouvre
-- (tu peux en ajouter autant que tu veux, il suffit de copier une ligne)
Config.Garages = {
    {
        label   = 'Garage Central',
        point   = vector3(215.8, -810.1, 30.7),   -- ou le joueur appuie sur E
        spawn   = vector3(229.5, -800.6, 30.6),   -- ou la trappe s'ouvre
        heading = 160.0,
        vehicles = { 'adder', 'zentorno', 't20', 'sultanrs' }, -- choix proposes
    },
}
