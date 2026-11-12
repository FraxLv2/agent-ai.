-- Relaye l'animation a tous les joueurs (avec anti-spam)
local last = {}

RegisterNetEvent('futur_garage:server:play', function(pos, heading, z)
    local src = source
    if type(pos) ~= 'vector3' or type(heading) ~= 'number' or type(z) ~= 'number' then return end

    local now = os.time()
    if last[src] and now - last[src] < Config.Cooldown then return end
    last[src] = now

    TriggerClientEvent('futur_garage:client:play', -1, pos, heading, z, src)
end)

AddEventHandler('playerDropped', function() last[source] = nil end)
