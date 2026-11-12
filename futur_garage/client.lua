-- =========================================================
--  futur_garage - client
--  Une trappe s'ouvre au sol, une plateforme monte avec la voiture.
--  Tout est fait avec les assets de base du jeu : aucun mapping,
--  aucun modele custom a installer.
-- =========================================================

local busy = false
local hatches = {}          -- animations de trappe en cours (locales + autres joueurs)
local myServerId = GetPlayerServerId(PlayerId())

local T = Config.Timings
local TOTAL = T.open + T.rise + T.hold + T.close

-- ---------- utilitaires ----------
local function notify(msg)
    BeginTextCommandThefeedPost('STRING')
    AddTextComponentSubstringPlayerName(msg)
    EndTextCommandThefeedPostTicker(false, true)
end

local function helpText(msg)
    BeginTextCommandDisplayHelp('STRING')
    AddTextComponentSubstringPlayerName(msg)
    EndTextCommandDisplayHelp(0, false, false, -1)
end

local function ease(x)
    if x <= 0.0 then return 0.0 elseif x >= 1.0 then return 1.0 end
    return x * x * (3.0 - 2.0 * x)
end

local function groundZ(pos)
    local found, z = GetGroundZFor_3dCoord(pos.x, pos.y, pos.z + 3.0, false)
    if found then return z end
    return pos.z - 1.0
end

local function loadModel(model)
    local hash = type(model) == 'number' and model or joaat(model)
    if not IsModelInCdimage(hash) or not IsModelAVehicle(hash) then return nil end
    RequestModel(hash)
    local limit = GetGameTimer() + 10000
    while not HasModelLoaded(hash) do
        if GetGameTimer() > limit then return nil end
        Wait(0)
    end
    return hash
end

local function loadPtfx(dict)
    RequestNamedPtfxAsset(dict)
    local limit = GetGameTimer() + 3000
    while not HasNamedPtfxAssetLoaded(dict) and GetGameTimer() < limit do Wait(0) end
    return HasNamedPtfxAssetLoaded(dict)
end

-- Ouverture des portes (0 = fermees, 1 = ouvertes) selon le temps ecoule
local function openProgress(t)
    if t < T.open then return ease(t / T.open) end
    if t < T.open + T.rise + T.hold then return 1.0 end
    return 1.0 - ease((t - T.open - T.rise - T.hold) / T.close)
end

-- ---------- dessin de la trappe ----------
local function box(x, y, z, heading, sx, sy, sz, c, a)
    DrawMarker(43, x, y, z, 0.0, 0.0, 0.0, 0.0, 0.0, heading, sx, sy, sz,
        c.r, c.g, c.b, a, false, false, 2, false, nil, nil, false)
end

local function drawHatch(h, now)
    local t = now - h.start
    local p = openProgress(t)
    local W, L = Config.Hatch.width, Config.Hatch.length
    local rad = math.rad(h.heading)
    local rx, ry = math.cos(rad), math.sin(rad)        -- axe droite
    local fx, fy = -math.sin(rad), math.cos(rad)       -- axe avant
    local x, y, z = h.pos.x, h.pos.y, h.z + 0.02
    local neon, plate, hole = Config.Colors.neon, Config.Colors.plate, Config.Colors.hole
    local pulse = math.floor(150 + 105 * math.sin(now / 150.0))

    -- trou noir (visible quand les portes s'ecartent)
    if p > 0.01 then
        box(x, y, z, h.heading, W, L, 0.03, hole, 255)
    end

    -- cadre neon autour de la trappe
    local e = 0.12
    box(x + rx * (W / 2 + e / 2), y + ry * (W / 2 + e / 2), z, h.heading, e, L + e * 2, 0.05, neon, pulse)
    box(x - rx * (W / 2 + e / 2), y - ry * (W / 2 + e / 2), z, h.heading, e, L + e * 2, 0.05, neon, pulse)
    box(x + fx * (L / 2 + e / 2), y + fy * (L / 2 + e / 2), z, h.heading, W, e, 0.05, neon, pulse)
    box(x - fx * (L / 2 + e / 2), y - fy * (L / 2 + e / 2), z, h.heading, W, e, 0.05, neon, pulse)

    -- deux portes metalliques qui glissent vers les cotes
    local half = W / 2
    for _, side in ipairs({ 1, -1 }) do
        local off = side * (half / 2 + p * half * 1.05)
        local px, py = x + rx * off, y + ry * off
        box(px, py, z + 0.04, h.heading, half, L, 0.06, plate, 255)
        -- bande lumineuse sur le bord interieur de chaque porte
        local inner = off - side * (half / 2 - 0.05)
        box(x + rx * inner, y + ry * inner, z + 0.08, h.heading, 0.08, L * 0.92, 0.03, neon, 255)
        -- lignes decoratives
        box(px + fx * (L * 0.25), py + fy * (L * 0.25), z + 0.08, h.heading, half * 0.7, 0.05, 0.02, neon, 120)
        box(px - fx * (L * 0.25), py - fy * (L * 0.25), z + 0.08, h.heading, half * 0.7, 0.05, 0.02, neon, 120)
    end

    -- plateforme qui arrive au ras du sol pendant la montee
    if t > T.open and p > 0.5 then
        local r = ease((t - T.open) / T.rise)
        if r > 0.85 then
            box(x, y, z + 0.01, h.heading, W * 0.95, L * 0.95, 0.04, plate, 255)
            box(x, y, z + 0.06, h.heading, W * 0.6, L * 0.6, 0.02, neon, math.floor(pulse * 0.5))
        end
    end

    -- lumiere qui sort du trou
    if p > 0.01 then
        DrawLightWithRange(x, y, z + 0.6, neon.r, neon.g, neon.b, 7.0, 4.0 * p)
        DrawLightWithRange(x, y, z + 2.5, neon.r, neon.g, neon.b, 5.0, 1.5 * p)
    end
end

-- un seul thread qui dessine toutes les trappes actives
local drawing = false
local function ensureDrawThread()
    if drawing then return end
    drawing = true
    CreateThread(function()
        while #hatches > 0 do
            local now = GetGameTimer()
            for i = #hatches, 1, -1 do
                local h = hatches[i]
                if now - h.start > TOTAL then
                    if h.smoke then StopParticleFxLooped(h.smoke, false) end
                    table.remove(hatches, i)
                else
                    drawHatch(h, now)
                end
            end
            Wait(0)
        end
        drawing = false
    end)
end

local function addHatch(pos, heading, z)
    local h = { pos = pos, heading = heading, z = z, start = GetGameTimer() }
    hatches[#hatches + 1] = h
    ensureDrawThread()

    -- effets : son + fumee pendant l'ouverture
    CreateThread(function()
        PlaySoundFromCoord(-1, 'CHECKPOINT_PERFECT', pos.x, pos.y, z, 'HUD_MINI_GAME_SOUNDSET', false, 30, false)
        if loadPtfx('core') then
            UseParticleFxAssetNextCall('core')
            h.smoke = StartParticleFxLoopedAtCoord('exp_grd_bzgas_smoke', pos.x, pos.y, z + 0.2,
                0.0, 0.0, 0.0, 0.6, false, false, false, false)
        end
        Wait(T.open + T.rise)
        if h.smoke then StopParticleFxLooped(h.smoke, false); h.smoke = nil end
        if loadPtfx('scr_rcbarry2') then
            UseParticleFxAssetNextCall('scr_rcbarry2')
            StartParticleFxNonLoopedAtCoord('scr_clown_appears', pos.x, pos.y, z + 0.5,
                0.0, 0.0, 0.0, 1.0, false, false, false)
        end
        PlaySoundFromCoord(-1, 'Beep_Red', pos.x, pos.y, z, 'DLC_HEIST_HACKING_SNAKE_SOUNDS', false, 30, false)
    end)
    return h
end

-- les autres joueurs voient aussi l'animation
RegisterNetEvent('futur_garage:client:play', function(pos, heading, z, owner)
    if owner == myServerId then return end
    if #(GetEntityCoords(PlayerPedId()) - pos) > Config.SyncDistance then return end
    addHatch(pos, heading, z)
end)

-- ---------- sortie du vehicule ----------
--- Sort un vehicule de facon futuriste.
--- @param model string|number  modele du vehicule
--- @param pos vector3          position de la trappe
--- @param heading number       orientation
--- @param cb function|nil      appelee avec le vehicule a la fin (cles, plaque, carburant...)
local function spawnFuturistic(model, pos, heading, cb)
    if busy then notify('~r~Une sortie est deja en cours.') return false end
    if IsAnyVehicleNearPoint(pos.x, pos.y, pos.z, 3.5) then
        notify('~r~L\'emplacement est occupe par un vehicule.') return false
    end

    local hash = loadModel(model)
    if not hash then notify('~r~Modele invalide : ' .. tostring(model)) return false end

    busy = true
    local z = groundZ(pos)
    local minDim = GetModelDimensions(hash)
    local finalZ = z - minDim.z
    local startZ = finalZ - Config.Hatch.depth

    -- la voiture attend sous le sol, invisible car cachee par le terrain
    local veh = CreateVehicle(hash, pos.x, pos.y, startZ, heading, true, false)
    SetModelAsNoLongerNeeded(hash)
    SetEntityCollision(veh, false, false)
    FreezeEntityPosition(veh, true)
    SetEntityInvincible(veh, true)
    SetVehicleDoorsLocked(veh, 2)
    SetVehicleEngineOn(veh, false, true, true)

    TriggerServerEvent('futur_garage:server:play', pos, heading, z)
    addHatch(pos, heading, z)

    CreateThread(function()
        Wait(T.open)

        -- montee de la plateforme
        SetVehicleLights(veh, 2)
        local s = GetGameTimer()
        while true do
            local k = (GetGameTimer() - s) / T.rise
            if k >= 1.0 then break end
            SetEntityCoordsNoOffset(veh, pos.x, pos.y, startZ + (finalZ - startZ) * ease(k), false, false, false)
            SetEntityHeading(veh, heading)
            Wait(0)
        end
        SetEntityCoordsNoOffset(veh, pos.x, pos.y, finalZ, false, false, false)

        -- la voiture est arrivee
        SetEntityCollision(veh, true, true)
        FreezeEntityPosition(veh, false)
        SetVehicleOnGroundProperly(veh)
        SetEntityInvincible(veh, false)
        SetVehicleDoorsLocked(veh, 1)
        SetVehicleLights(veh, 0)
        SetVehicleEngineOn(veh, true, true, false)

        if Config.WarpIntoVehicle then
            TaskWarpPedIntoVehicle(PlayerPedId(), veh, -1)
        end
        busy = false
        if cb then cb(veh) end
    end)
    return true
end

-- utilisable depuis un autre script (ESX / QBCore / garage existant) :
-- exports['futur_garage']:SpawnVehicleFuturistic('adder', vector3(x, y, z), heading, function(veh) end)
exports('SpawnVehicleFuturistic', spawnFuturistic)

-- ---------- commande de test ----------
if Config.Command then
    RegisterCommand(Config.Command, function(_, args)
        local ped = PlayerPedId()
        if IsPedInAnyVehicle(ped, false) then notify('~r~Descends du vehicule d\'abord.') return end
        local heading = GetEntityHeading(ped)
        local pos = GetOffsetFromEntityInWorldCoords(ped, 0.0, Config.SpawnDistance, 0.0)
        spawnFuturistic(args[1] or Config.DefaultModel, pos, (heading + 90.0) % 360.0)
    end, false)
    TriggerEvent('chat:addSuggestion', '/' .. Config.Command, 'Sortir une voiture du sol', {
        { name = 'modele', help = 'ex: adder, zentorno, t20' }
    })
end

-- ---------- points de garage ----------
CreateThread(function()
    for _, g in ipairs(Config.Garages) do
        local b = AddBlipForCoord(g.point.x, g.point.y, g.point.z)
        SetBlipSprite(b, 357); SetBlipColour(b, 3); SetBlipScale(b, 0.8); SetBlipAsShortRange(b, true)
        BeginTextCommandSetBlipName('STRING'); AddTextComponentSubstringPlayerName(g.label); EndTextCommandSetBlipName(b)
    end

    local choice = {}
    while true do
        local sleep = 1000
        local ped = PlayerPedId()
        local coords = GetEntityCoords(ped)
        for i, g in ipairs(Config.Garages) do
            local d = #(coords - g.point)
            if d < 20.0 then
                sleep = 0
                local n = Config.Colors.neon
                DrawMarker(27, g.point.x, g.point.y, g.point.z - 0.97, 0, 0, 0, 0, 0, 0, 1.5, 1.5, 1.0,
                    n.r, n.g, n.b, 180, false, false, 2, true, nil, nil, false)
                if d < 1.6 and not busy and not IsPedInAnyVehicle(ped, false) then
                    choice[i] = choice[i] or 1
                    local list = g.vehicles
                    helpText(('~INPUT_CELLPHONE_LEFT~ ~INPUT_CELLPHONE_RIGHT~ Vehicule : ~b~%s~s~ (%d/%d)\n~INPUT_CONTEXT~ Sortir le vehicule')
                        :format(list[choice[i]], choice[i], #list))
                    if IsControlJustPressed(0, 174) then choice[i] = (choice[i] - 2) % #list + 1 end
                    if IsControlJustPressed(0, 175) then choice[i] = choice[i] % #list + 1 end
                    if IsControlJustPressed(0, 38) then
                        spawnFuturistic(list[choice[i]], g.spawn, g.heading)
                    end
                end
            end
        end
        Wait(sleep)
    end
end)
