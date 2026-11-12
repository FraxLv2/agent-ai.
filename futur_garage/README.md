# futur_garage — Sortie de véhicule futuriste (FiveM)

Quand on sort une voiture : un cadre néon s'allume au sol, deux portes métalliques
s'écartent, de la fumée et de la lumière sortent du trou, puis la voiture **monte du sol**
sur une plateforme. Les portes se referment ensuite.

✅ Aucun mapping, aucun modèle Blender à installer : tout utilise les éléments du jeu de base.
✅ Standalone (marche avec ESX, QBCore ou sans framework).
✅ Les autres joueurs proches voient aussi l'animation.

## Installation
1. Copie le dossier `futur_garage` dans le dossier `resources` de ton serveur.
2. Ajoute dans `server.cfg` :
   ```
   ensure futur_garage
   ```
3. Redémarre le serveur (ou tape `refresh` puis `ensure futur_garage` dans la console).

## Tester
- En jeu : `/sortirvoiture` ou `/sortirvoiture zentorno`
- Ou va au point de garage (blip « Garage Central » près de Legion Square) :
  flèches ⬅️ ➡️ pour choisir, **E** pour sortir la voiture.

## Réglages (`config.lua`)
- `Config.Garages` : ajoute tes garages (point où appuyer sur E + endroit où la trappe s'ouvre).
  Pour récupérer des coordonnées en jeu, place-toi au bon endroit et utilise un script de coords
  (ou `/coords` si ton serveur en a un).
- `Config.Hatch` : taille de la trappe. `Config.Timings` : vitesse de l'animation.
- `Config.Colors.neon` : couleur des néons. `Config.Command = false` pour désactiver la commande.

## Brancher sur ton garage existant (ESX / QBCore)
Dans ton script de garage, remplace l'endroit qui crée la voiture par :
```lua
exports['futur_garage']:SpawnVehicleFuturistic(model, vector3(x, y, z), heading, function(veh)
    -- ici : plaque, propriétés, clés, essence... (ce que ton garage faisait déjà)
end)
```
