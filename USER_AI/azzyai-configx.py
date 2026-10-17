#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AzzyAI Config X — Reconstrucción multiplataforma de AzzyAIConfig.exe
====================================================================
Reconstrucción funcional de la interfaz del configurador original de AzzyAI
(decompilado con REA: .NET Framework 4.0 WinForms, assembly 1.5.0.0).

Ejecución:      python3 azzyai-configx.py [--ai-dir RUTA] [--no-browser] [--port N]
Funciona en:    Linux, Windows, macOS (solo Python 3 stdlib, cero dependencias)
Editar:         H_Config.lua, M_Config.lua, H_Tactics.lua, M_Tactics.lua,
                H_PVP_Tact.lua, M_PVP_Tact.lua, H_Extra.lua, M_Extra.lua
"""
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from urllib.parse import urlparse

# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------

def script_dir():
    if getattr(sys, "frozen", False):  # PyInstaller onefile: usar el dir del ejecutable
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------
# Enums (reconstruidos del exe + semántica del código Lua de AzzyAI)
# ----------------------------------------------------------------------------

ENUMS = {
    "uskillonly": [(-1, "Chase — skills al perseguir y atacar (recomendado)"),
                   (0, "Attacking — skills solo al atacar"),
                   (1, "Skill only — solo skills, nunca ataque normal")],
    "uattackskill": [(0, "No"), (1, "Sí")],
    "oldhomuntype": [(0, "Lif"), (1, "Amistr"), (2, "Filir"), (3, "Vanilmirth")],
    "autoheal": [(0, "Nunca"), (1, "Siempre"), (2, "Solo cuando idle (entre kills)"),
                 (3, "Solo si no hay nada que hacer")],
    "buffmode": [(0, "Nunca"), (1, "Cuando idle"), (2, "Mientras persigue"),
                 (3, "Idle / HP bajo"), (4, "Berserk"), (5, "ASAP (siempre)")],
    "automag": [(0, "Off"), (1, "Self"), (2, "All")],
    "automob": [(0, "Disabled"), (1, "Aggressive"), (2, "All")],
    "autocombo": [(0, "Never"), (1, "Tactics"), (2, "Always")],
    "idlewalk": [(0, "None"), (1, "Circle"), (2, "Cross"), (3, "Square"),
                 (4, "Random"), (5, "Route Lineal"), (6, "Route Circular")],
    "stickystandby": [(0, "Disabled"), (1, "Enabled"), (2, "Enabled + Relog")],
    "autopushback": [(0, "Never"), (1, "Idle"), (2, "Chase"), (3, "Idle, HP bajo"), (4, "Berserk")],
    "onoff": [(0, "Off"), (1, "On")],
    "tact_basic": [(-2, "Tank mobs"), (-1, "Tank"), (0, "Ignore"),
                   (2, "Attack (low)"), (3, "Attack (medium)"), (4, "Attack (high)"),
                   (5, "React (low)"), (7, "React (medium)"), (8, "React (high)"),
                   (9, "React (self)"), (10, "Snipe (low)"), (11, "Snipe (medium)"),
                   (12, "Snipe (high)"), (13, "Attack (low) React (medium)"),
                   (14, "Attack (last)"), (15, "Attack (top)")],
    "tact_kite": [(0, "Never"), (1, "React"), (2, "Always")],
    "tact_cast": [(0, "Passive (ignorar casts)"), (1, "React (básico)"),
                  (9, "React w/Any"), (10, "React w/Main"), (11, "React w/S"),
                  (12, "React w/Mob"), (13, "React w/Debuff"), (15, "React w/Minions"),
                  (8026, "React w/Silent Breeze"), (8043, "React w/Volcanic Ash"),
                  (8211, "React w/Sandman"), (8212, "React w/Freeze Trap"),
                  (8225, "React w/Crash"), (8232, "React w/Provoke"),
                  (8234, "React w/Decrease Agi"), (8236, "React w/Lex Divina")],
    "tact_push": [(0, "Never"), (1, "Off self"), (2, "Off self + friend")],
    "tact_debuff": [(0, "Never"), (-1, "Any (reactivo)"), (-8026, "Silent Breeze"), (-8043, "Volcanic Ash"),
                    (-8211, "Sandman"), (-8212, "Freeze Trap"), (-8225, "Crash"),
                    (-8232, "Provoke"), (-8234, "Decrease Agi"), (-8236, "Lex Divina"),
                    (1, "Any (proactivo)"), (8026, "Silent Breeze"), (8043, "Volcanic Ash"),
                    (8211, "Sandman"), (8212, "Freeze Trap"), (8225, "Crash"),
                    (8232, "Provoke"), (8234, "Decrease Agi"), (8236, "Lex Divina")],
    "tact_class": [(-1, "Any skill"), (0, "Non-Homun S skills"), (1, "Homun S skills"),
                   (2, "Mob skills"), (3, "Combo (first skill)"), (4, "Combo (full combos)"),
                   (5, "Summon minions"), (6, "Grapple (Tinder Breaker)"),
                   (7, "Grapple (CBC)"), (8, "Grapple (EQC)"),
                   (9, "Minions + Pre-S skill"), (10, "Minions + Homun S")],
    "tact_rescue": [(0, "Never"), (1, "Friends"), (2, "Owner's merc/retainer"),
                    (3, "Self (homunculus)"), (4, "Owner"), (5, "All of the above")],
    "tact_snipe": [(1, "Snipe OK"), (0, "Snipe disabled")],
    "tact_ks": [(0, "Never"), (1, "Always"), (-1, "Polite")],
    "tact_chase": [(-1, "Normal"), (0, "Always"), (1, "Never"), (2, "Clever")],
}

# ----------------------------------------------------------------------------
# Opciones del homúnculo (128 campos del H_Config del exe original)
# (nombre, categoría, enum|None)
# ----------------------------------------------------------------------------

_HOM = [
    # Basic
    ("AggroHP", "Basic", None), ("AggroSP", "Basic", None),
    ("KiteMonsters", "Basic", "onoff"),
    ("PainkillerFriends", "Basic", "onoff"), ("PainkillerFriendsSave", "Basic", "onoff"),
    ("SuperPassive", "Basic", "onoff"), ("UseAttackSkill", "Basic", "uattackskill"),
    ("AssumeHomun", "Basic", "onoff"), ("DoNotChase", "Basic", "onoff"),
    ("UseDanceAttack", "Basic", "onoff"), ("UseAvoid", "Basic", "onoff"),
    ("TankMonsterLimit", "Basic", None), ("RescueOwnerLowHP", "Basic", None),
    ("StationaryAggroDist", "Basic", None), ("MobileAggroDist", "Basic", None),
    ("OldHomunType", "Basic", "oldhomuntype"), ("OpportunisticTargeting", "Basic", "onoff"),
    ("AttackLastFullSP", "Basic", "onoff"), ("DanceMinSP", "Basic", None),
    ("AttackTimeLimit", "Basic", None), ("LagReduction", "Basic", None),
    ("DoNotAttackMoving", "Basic", "onoff"), ("LiveMobID", "Basic", None),
    # AutoSkill
    ("AttackSkillReserveSP", "AutoSkill", None), ("AutoMobCount", "AutoSkill", None),
    ("UseSkillOnly", "AutoSkill", "uskillonly"), ("AutoSkillDelay", "AutoSkill", None),
    ("AutoSkillLimit", "AutoSkill", None), ("UseAutoPushback", "AutoSkill", "autopushback"),
    ("AutoPushbackThreshold", "AutoSkill", None), ("AoEReserveSP", "AutoSkill", None),
    ("AoEFixedLevel", "AutoSkill", None), ("AutoMobMode", "AutoSkill", "automob"),
    ("AutoComboMode", "AutoSkill", "autocombo"), ("AutoComboSpheres", "AutoSkill", None),
    ("UseHomunSSkillChase", "AutoSkill", "onoff"), ("UseHomunSSkillAttack", "AutoSkill", "onoff"),
    ("AoEMaximizeTargets", "AutoSkill", "onoff"),
    ("UseEiraXenoSlasher", "AutoSkill", "buffmode"), ("EiraXenoSlasherLevel", "AutoSkill", None),
    ("UseEiraSilentBreeze", "AutoSkill", "buffmode"), ("EiraSilentBreezeLevel", "AutoSkill", None),
    ("UseEiraEraseCutter", "AutoSkill", "buffmode"), ("EiraEraseCutterLevel", "AutoSkill", None),
    ("UseBayeriStahlHorn", "AutoSkill", "onoff"), ("BayeriStahlHornLevel", "AutoSkill", None),
    ("UseBayeriHailegeStar", "AutoSkill", "onoff"), ("BayeriHailegeStarLevel", "AutoSkill", None),
    ("UseSeraParalyze", "AutoSkill", "onoff"), ("SeraParalyzeLevel", "AutoSkill", None),
    ("UseSeraPoisonMist", "AutoSkill", "buffmode"), ("SeraPoisonMistLevel", "AutoSkill", None),
    ("UseEleanorSonicClaw", "AutoSkill", "onoff"), ("EleanorSonicClawLevel", "AutoSkill", None),
    ("EleanorSilverveinLevel", "AutoSkill", None), ("EleanorMidnightLevel", "AutoSkill", None),
    ("EleanorDoNotSwitchMode", "AutoSkill", "onoff"),
    ("UseDieterLavaSlide", "AutoSkill", "buffmode"), ("UseDieterVolcanicAsh", "AutoSkill", "onoff"),
    ("DieterLavaSlideLevel", "AutoSkill", None),
    ("UseSeraCallLegion", "AutoSkill", "onoff"), ("SeraCallLegionLevel", "AutoSkill", None),
    # Walk / Follow
    ("FollowStayBack", "Walk/Follow", None), ("RestXOff", "Walk/Follow", None),
    ("RestYOff", "Walk/Follow", None), ("DoNotUseRest", "Walk/Follow", "onoff"),
    ("SpawnDelay", "Walk/Follow", None), ("MoveSticky", "Walk/Follow", None),
    ("MoveStickyFight", "Walk/Follow", None), ("UseIdleWalk", "Walk/Follow", "idlewalk"),
    ("IdleWalkSP", "Walk/Follow", None), ("UseCastleRoute", "Walk/Follow", "onoff"),
    ("RelativeRoute", "Walk/Follow", "onoff"), ("IdleWalkDistance", "Walk/Follow", None),
    ("ChaseSPPause", "Walk/Follow", "onoff"), ("ChaseSPPauseSP", "Walk/Follow", None),
    ("ChaseSPPauseTime", "Walk/Follow", None),
    ("StationaryMoveBounds", "Walk/Follow", None), ("MobileMoveBounds", "Walk/Follow", None),
    # Autobuff
    ("UseOffensiveBuff", "Autobuff", "buffmode"), ("UseDefensiveBuff", "Autobuff", "buffmode"),
    ("LifEscapeLevel", "Autobuff", None), ("FilirFlitLevel", "Autobuff", None),
    ("AmiBulwarkLevel", "Autobuff", None), ("HealOwnerHP", "Autobuff", None),
    ("UseAutoHeal", "Autobuff", "autoheal"), ("HealOwnerBreeze", "Autobuff", "onoff"),
    ("FilirAccelLevel", "Autobuff", None), ("UseSeraPainkiller", "Autobuff", "buffmode"),
    ("DefensiveBuffOwnerMobbed", "Autobuff", None),
    ("UseBayeriAngriffModus", "Autobuff", "buffmode"), ("UseBayeriGoldenPherze", "Autobuff", "buffmode"),
    ("UseDieterMagmaFlow", "Autobuff", "buffmode"), ("UseDieterGraniticArmor", "Autobuff", "buffmode"),
    ("UseDieterPyroclastic", "Autobuff", "buffmode"), ("UseEiraOveredBoost", "Autobuff", "buffmode"),
    ("HealSelfHP", "Autobuff", None), ("LavaSlideMode", "Autobuff", "buffmode"),
    ("PoisonMistMode", "Autobuff", "buffmode"),
    ("UseBayeriSteinWand", "Autobuff", "buffmode"), ("BayeriSteinWandLevel", "Autobuff", None),
    ("UseSteinWandSelfMob", "Autobuff", None), ("UseSteinWandOwnerMob", "Autobuff", None),
    ("UseSteinWandTele", "Autobuff", "onoff"), ("SteinWandTelePause", "Autobuff", None),
    ("UseCastleDefend", "Autobuff", "onoff"), ("CastleDefendThreshold", "Autobuff", None),
    ("UseSmartBulwark", "Autobuff", "onoff"),
    # Kiting
    ("KiteParanoid", "Kiting", "onoff"), ("KiteStep", "Kiting", None),
    ("KiteParanoidStep", "Kiting", None), ("KiteThreshold", "Kiting", None),
    ("KiteParanoidThreshold", "Kiting", None), ("KiteBounds", "Kiting", None),
    ("ForceKite", "Kiting", "onoff"), ("FleeHP", "Kiting", None),
    # Friending
    ("StandbyFriending", "Friending", None), ("MirAIFriending", "Friending", None),
    # Standby
    ("DefendStandby", "Standby", None), ("StickyStandby", "Standby", "stickystandby"),
    # Berserk
    ("UseBerserkMobbed", "Berserk", None), ("UseBerserkSkill", "Berserk", "onoff"),
    ("UseBerserkAttack", "Berserk", "onoff"), ("Berserk_SkillAlways", "Berserk", "onoff"),
    ("Berserk_Dance", "Berserk", "onoff"), ("Berserk_IgnoreMinSP", "Berserk", "onoff"),
    ("Berserk_ComboAlways", "Berserk", "onoff"),
    # PVP
    ("PVPmode", "PVP", None),
]

# Metadata extra para opciones de mercenario conocidas (enums + categorías)
_MER_META = {
    "UseSkillOnly": ("AutoSkill", "uskillonly"), "UseAutoMag": ("Autobuff", "automag"),
    "UseAutoSight": ("Autobuff", "onoff"), "UseProvokeOwner": ("Autobuff", "buffmode"),
    "UseProvokeSelf": ("Autobuff", "buffmode"), "UseSacrificeOwner": ("Autobuff", "buffmode"),
    "UseBlessingSelf": ("Autobuff", "buffmode"), "UseBlessingOwner": ("Autobuff", "buffmode"),
    "UseKyrieSelf": ("Autobuff", "buffmode"), "UseKyrieOwner": ("Autobuff", "buffmode"),
    "UseIncAgiSelf": ("Autobuff", "buffmode"), "UseIncAgiOwner": ("Autobuff", "buffmode"),
    "UseOffensiveBuff": ("Autobuff", "buffmode"), "UseDefensiveBuff": ("Autobuff", "buffmode"),
    "UseAutoPushback": ("AutoSkill", "autopushback"), "AutoMobMode": ("AutoSkill", "automob"),
    "AutoComboMode": ("AutoSkill", "autocombo"), "UseIdleWalk": ("Walk/Follow", "idlewalk"),
    "StickyStandby": ("Standby", "stickystandby"), "KiteMonsters": ("Basic", "onoff"),
    "UseAttackSkill": ("Basic", "uattackskill"), "SuperPassive": ("Basic", "onoff"),
    "DoNotChase": ("Basic", "onoff"), "UseDanceAttack": ("Basic", "onoff"),
    "AssumeHomun": ("Basic", "onoff"), "AutoDetectPlant": ("Basic", "onoff"),
    "LiveMobID": ("Basic", None), "LagReduction": ("Basic", None),
    "UseAvoid": ("Basic", "onoff"), "KSMercHomun": ("Basic", "onoff"),
    "FleeHP": ("Kiting", None), "ForceKite": ("Kiting", "onoff"),
    "KiteParanoid": ("Kiting", "onoff"), "KiteBounds": ("Kiting", None),
    "KiteStep": ("Kiting", None), "KiteParanoidStep": ("Kiting", None),
    "KiteThreshold": ("Kiting", None), "KiteParanoidThreshold": ("Kiting", None),
    "PVPmode": ("PVP", None), "UseBerzerkMobbed": ("Berserk", None),
    "UseBerzerkSkill": ("Berserk", "onoff"), "UseBerzerkAttack": ("Berserk", "onoff"),
    "Berzerk_SkillAlways": ("Berserk", "onoff"), "Berzerk_Dance": ("Berserk", "onoff"),
    "Berzerk_IgnoreMinSP": ("Berserk", "onoff"),
    "UseBerserkMobbed": ("Berserk", None), "UseBerserkSkill": ("Berserk", "onoff"),
    "UseBerserkAttack": ("Berserk", "onoff"),
    "StandbyFriending": ("Friending", None), "MirAIFriending": ("Friending", None),
    "NewAutoFriend": ("Friending", "onoff"), "DefendStandby": ("Standby", None),
    "UseAutoChaoticBless": ("Autobuff", None), "ChaoticBlessLevel": ("Autobuff", None),
    "ChaoticBlessHP": ("Autobuff", None),
}

# Tooltips extraídos de Documentation.pdf (embebidos)
TIPS = {
"AggressiveAutofriend": "Additional option for Autofriending. This will much more aggressively synchronize friending between multiple accounts running on one computer you do not need to walk off screen, and resummoning homunculus will not confuse it. This relies on frequently checking H_ID/M_ID files, and may result in poor performance on slower machines. Set AggressiveAutofriend =1 in H_Extra/M_Extra to enable this…",
"AggressiveRelogTracking": "Uncomment this line to enable much more rigorous tracking of relog events for tracking of skill durations. This is done by repetitively writing a file to record when the homunculus is not logged in. This generates a large amount of disk activity, and may result in performance degradation on some systems. You can specify where to store this file using AggressiveRelogPath – if you have a…",
"AllowSBR44": "If this is set to 0 (the default), the AI will block any attempt to manually cast SBR44. This is to help prevent accidental use of the skill. Unfortunately I can’t find a way to do the same thing for Self Destruct, which is much easier to accidentally use. Options relating to use of buff skills For each buff skill, you can set it to be used at different times depending on what you set the option…",
"AmiBulwarkLevel": "This is the level of Amistr Bulwark to use. Default is 5.",
"AoE": "if this was 0, it will not use an AoE (as it would only hit 1 target). If this was 1, it would use the skill on the stack of monsters to the northeast, resulting in it not hitting it’s current target, but hitting the whole stack of monsters).",
"AoEFixedLevel": "If the homunculus has a mob attack, it will always use the level specified by the (homunculus S type)(homunculus s skill name)Level option, regardless of tactics skill level settings. homunculus only, defaults to 1.",
"AoEMaximizeTargets": "Set this to 1 to try to hit as many targets as possible with AoE attacks, at the risk of aggroing additional monsters and not hitting the original target (for example, if there are a large number of monsters stacked up on the northeast side of the homunculus, as it attacks a solitary monster to the southwest, using a skill with a 3x3",
"AoEReserveSP": "If this is set to 1, attack skills will not be used if doing so would leave the homunculus without enough SP to use it’s AoE skill",
"AssumeHomun": "With this set to 1, the homunculus will attempt to automatically friend the owner’s mercenary (and vice-versa). Set to 0 only if you (for whatever reason) do not want your homunculus to “ks” your mercenary (or vice-versa)",
"Attack": "Low (TACT_ATTACK_L): Seek out and attack this monster only if there are no higher priority targets, and do not prioritize attacking this monster if it is currently attacking the homunculus or owner/friend.",
"AttackLastFullSP": "For monsters where the tactic is set to ATTACK_LAST, if this is enabled, these monsters will be attacked only if the homunculus has 100% SP (this is a good setting for event monsters and plants, where you don’t want them sacrificing any SP regen to kill them, but might as well kill them when at full SP.",
"AttackSkillReserveSP": "The homunculus will not use offensive skills if they would leave it with less than this amount of SP. This is overridden on a per-monster basis by TACT_SP. The purpose of this option is to keep a reserve of SP for emergencies (via BerserkMode and Berserk_IgnoreMinSP), or particularly dangerous monsters (via TACT_SP) and/or to ensure that homunculus reserves enough SP to maintain buffs. For…",
"AutoMobCount": "If the mercenary/homunculus has a mob attack, it will use it only if there are at least this many targets attacking it. This is subject to the Weight tactic (see below)",
"AutoPushbackThreshold": "This is the distance between the mercenary and target at which the mercenary will attempt to use a pushback skill on it. Mercenary only.",
"AutoSkillDelay": "homunculus will wait this long between trying to use skills, even those with no skill cooldown, to prevent problems like “double casting” of skills. This is the length of the delay in milliseconds.",
"AutoSkillLimit": "Set this to a number to limit the number of times an offensive skill will be used on any target. This can be overridden by tactics settings.",
"Autofriending": "If you have multiple accounts running on the same computer, and want their homuns to help each other, friend the players (this should be done by hand, due to race conditions, since friend list is shared by all homuns running from a specific locations - but if you insist on doing it through the game, only have one homunculus out at a time while friending). AzzyAI will attempt to detect their…",
"BasicDebuffs": "In this section, you can configure which debuffs will be used if debuffs are enabled, but no specific debuff is specified in Tactics. Set a debuff to 1 to enable use of it.",
"BayeriHailageStarLevel": "Use this level of the Bayeri skill, Hailage Star.",
"BayeriStahlHornLevel": "Use this level of the Bayeri skill, Stahl Horn.",
"BayeriSteinWandLevel": "Use this level of the Stein Wand.",
"Berzerk_Dance": "Set to 1 to use dance attack when in berserk mode (homunculus only).",
"Berzerk_IgnoreMinSP": "Set to 1 to ignore AttackSkillReserveSP when in berserk mode. Options related to Kiting When using archer mercenaries, it is frequently advantageous for the mercenary to try to run away from monsters that try to attack it, while attacking them. This is called kiting (pronounced kite-ing). The default values for the kiting steps, thresholds, and bounds have been chosen empirically – you should not…",
"Berzerk_SkillAlways": "Set to 1 to always use offensive skills when in berserk mode.",
"CastleDefendThreshold": "If UseCastleDefend = 1 then castling will be cast when there are at least this many monsters on the owner. The Weight tactic does apply to this.",
"ChaseSPPause": "When this is set to 1, the homunculus will delay chasing monsters and following of the owner immediately before an SP-regen tick, and will wait until that SP regen tick occurs before moving. This can be overridden on a per-monster basis by TACT_CHASE; if set to CHASE_ALWAYS for a monster, it will disregard this consideration.",
"ChaseSPPauseSP": "If ChaseSPPause is enabled, it will be used when the homunculus has less than this much SP. If specified as a negative number, it will be treated as a percentage.",
"ChaseSPPauseTime": "If ChaseSPPause is enabled, this is the maximum time (in milliseconds) that the homunculus will wait for an SP tick (if an SP tick is farther away than this, it will not try to wait for it). Options relating to use of attack skills",
"DefendStandby": "If set to 1, when homunculus is placed in standby mode using alt+t, it will continue to defend the owner.",
"DefensiveBuffOwnerHP": "If DefensiveBuffOwnerMobbed is set to a non-zero number, Painkiller and Kyrie Eleison if the owner's HP as a percentage is higher than DefensiveBuffOwnerHP.",
"DefensiveBuffOwnerMobbed": "If this is set to a non-zero number, Painkiller and Kyrie Eleison will not be used on the owner if there are less than this many monsters on the owner, AND the owner is below an HP threshold set by DefensiveBuffOwnerHP.",
"DieterLavaSlideLevel": "Use this level of the Dieter skill, Lava Slide. See LavaSlideMode.",
"DoNotAttackMoving": "Set to 1 to not attack moving monsters. This may help prevent wasted time against fast moving targets, kill-stealing from people mobbing monsters, and so on. Obviously, it is unsuitable for use while AFK leveling in OD2 for example.",
"DoNotUseRest": "When this is set to 1, the homunculus will not “rest” when the owner sits.",
"EiraEraseCutterLevel": "Use this level of the Eira skill, Erase Cutter.",
"EiraXenoSlasherLevel": "Use this level of the Eira skill, Xeno Slasher.",
"EleanorCBCLevel": "Use this level of the Eleanor skill, C. B. C.",
"EleanorDoNotSwitchMode": "Normally, we try to track what mode we’re in and correct it with Style Change. It has been found that this does not always provide acceptable behavior, due to challenges in determining what mode the homunculus is in. If EleanorDoNotSwitchMode is set to 1, we instead assume we are always in the right mode, and will never autocast Style Change – it is up to the owner to make sure it is in the right…",
"EleanorEQCLevel": "Use this level of the Eleanor skill, E. Q. C.",
"EleanorMidnightLevel": "Use this level of the Eleanor skill, Midnight Frenzy.",
"EleanorSilverveinLevel": "Use this level of the Eleanor skill, Silvervein Rush.",
"EleanorSonicClawLevel": "Use this level of the Eleanor skill, Sonic Claw.",
"EleanorTinderBreakerLevel": "Use this level of the Eleanor skill, Tinder Breaker.",
"Example": "Relative route for heart-shaped idle walk: UseIdleWalk=6 (Route – Circular) RelativeRoute=1",
"FilerFlitLevel": "This is the level of Flitting to use. Default is 1.",
"FilirAccelLevel": "This is the level of Accelerated Flight to use. Default is 1. Zero (0) is not a valid value – disable use of Accelerated Flight using UseAutoGuard.",
"FleeHP": "Only kite when below this much hp, as a percentage. Set to 0 to ignore this condition. Other Options These options may be used to tune behavior, particularly on laggy connection.",
"FollowStayBack": "Your homunculus will stay this many cells behind you when following you. StationaryMoveBounds, MobileMoveBounds – This is the distance from the owner, in cells, within which the homunculus may move, for example, to respond to attacks, while the owner stationary or moving, respectively. If it finds itself beyond this distance, it will drop everything to try to get back to you. These options should…",
"FriendAttack": "In this section, you can configure which motions, on the part of the owner of a friend, should be interpreted as offensive acts, and hence a cue for the homunculus to attack the targeted monster. Set them to 1 to treat them as offensive acts.",
"GUI": "use the TACT_SIZE tactic, SIZE_LARGE is the same as CLASS_MOB, SIZE_UNDEFINED should be used in all other cases (since there's no S-class skills for mercenary) • Unified code between chase skill use and attack skill use • Fixed longstanding issue with debuff while attacking which would prevent the homunculus from using debuffs while attacking if told via tactics to use a certain debuff skill.…",
"HealOwnerBreeze": "Set this to 1 to have the AI use Silent Breeze to heal it’s owner (in accordance with above UseAutoHeal, HealOwnerHP) if available. This should only be enabled if you’re on a server with the silent breeze nerf AND you have 100% silence resist. HealOwnerHP – This is the owner’s HP, as a percentage, below which the homunculus will attempt to use a healing skill to heal the owner (assuming…",
"HealSelfHP": "For a Vanilmirth with Chaotic Blessings, set this to the HP (as a percentage) at which the homunculus will use Chaotic Blessings (level 4, see note above for when it will use level 5) to heal itself. This does not work for Lif, as Healing Hands can only heal the owner.",
"IdleWalkDistance": "For circle, cross, square, or random idle-walk, move this far from owner.",
"IdleWalkSP": "When SP (as a percentage) is lower than this, do not use IdleWalk.",
"KiteBounds": "This is the maximum distance the homunculus will move from owner to kite. Must be less than MoveBounds.",
"KiteMonsters": "Set this to 1 to enable kiting.",
"KiteParanoid": "Set this to 1 to default to kiting before being attacked. This can be overridden by tactics settings.",
"KiteParanoidStep": "This is the number of cells that homunculus will move when kiting before being attacked. Leave at 2 unless you need the homunculus to be unusually fearful.",
"KiteParanoidThreshold": "How close a monster has to be before triggering kiting without being attacked.",
"KiteStep": "This is the number of cells that homunculus will move to kite. Leave at 5 unless you have good reason to change.",
"KiteThreshold": "How close a monster has to be before triggering kiting, when monster has attacked homunculus. 3 works pretty well.",
"LagReduction": "On some servers, a peculiar type of lag is observed on crowded or heavily loaded maps, where both the player and homun lag when the homunculus is out, but lag is not observed with the homun not out. Setting this to 1 (true) will try to reduce the number of commands the homun sends; this has the disadvantage of reducing responsiveness on servers that don’t lag. This setting is recommended for all…",
"LavaSlideMode": "If set to 0, Lava Slide will be used as a normal AoE attack. Otherwise, it will be kept up centered on owner, in which case, this controls when to use it. It is recommended to set this to 1 when AFK leveling on crowded maps, as it will improve exp/hr and cause less disruption to other players on the map. Setting this to ASAP is not recommended. UseProvokeOwner (mercenary only) – This controls use…",
"LifEscapeLevel": "This is the level of Urgent Escape to use. Default is 5. Zero (0) is not a valid value – disable use of Accelerated Flight using UseAutoQuicken.",
"LiveMobID": "If this is enabled, on both mercenary AND homun, both owned by same player and out simultaneously, the homunculus will record monster ID’s continuously, while the mercenary loads it. It will be written to the AggressiveRelogPath, because this will generate a lot of disk activity. Whenever merc and homun are used simultaneously, it is recommended to enable LagReduction.",
"MirAIFriending": "Set to 1 (default) to emulate MirAI friending. Tactics Through the tactics system, it is possible to configure your mercenary or homunculus to treat different types of monsters differently – for example, prioritizing powerful monsters, and ignoring plants and mushrooms. Mercenaries and tactics Mercenaries cannot identify monsters. In order for any entry other than the default entry to be used on…",
"MoveSticky": "If set to 1, if you command your homunculus to move, it will stay there, and not return to you, until you tell it to move again.",
"MoveStickyFight": "If set to 1, when your homunculus is in the above “sticky move” state, it will still fight normally.",
"NewAutoFriend": "Uncomment the NewAutoFriend = 0 line if you are using an AI other than AzzyAI for your mercenary (if this is for the homunculus) or vise versa. If this option is used, you must summon your mercenary and homunculus, and then relog or teleport in order to trigger the friending.",
"OldHomunType": "For homunculus S, this value is used to determine what the homunculus was in its past life. For your convenience, the three possibilities are listed in H_Extra.lua, and you need only comment out the incorrect option (by adding “--“ in front of it) and uncomment the correct option (by removing the “--\" in front of it). This setting is ignored if your homunculus was previously a Vanilmirth;…",
"PVPmode": "Set to 1 to enable PVP functionality",
"PainkillerFriends": "Set to 1 to auto-painkiller friended players. Players will be added to the painkiller list if you manually command the homunculus to use Painkiller on them",
"PainkillerFriendsSave": "Set to 1 if using PainkillerFriends to have homunculus remember players who you have prescribed painkillers to. Options related to other skills",
"PoisonMistMode": "If set to 0, Poison Mist will be used as a normal AoE attack. Otherwise, it will be kept up centered on owner, in which case, this controls when to use it. It is recommended to set this to 1 when AFK leveling on crowded maps, as it will improve exp/hr and cause less disruption to other players on the map. Setting this to ASAP is not recommended.",
"ProvokeOwnerMobbed": "If this is set to a non-zero number, provoke or painkiller will not be used on the owner if there are less than this many monsters on the owner, AND the owner is below 90% hp. TACT_WEIGHT applies here.",
"RESCUE_ALL": "All of the above except self. SP Tactics If this value is set to a positive number, that value will be used instead of AttackSkillReserveSP when fighting this monster. Otherwise, AttackSkillReserveSP will be used normally. By setting a higher value for weak monsters, you can keep SP in reserve for the stronger monsters, without entirely disabling skill use on the weaker ones. Snipe Tactics This…",
"RESCUE_OWNER": "Rescue the owner.",
"RESCUE_SELF": "Drop everything to defend self against this.",
"React": "Low (TACT_REACT_L): Attack this monster when self/owner/friend attacked, low priority. Attack – Medium and Attack – High take priority over this, and do not prioritize attacking this monster if it is currently attacking the homunculus or owner/friend.",
"RelativeRoute": "Route is specified in relative terms (see Route Walk in advanced options) RestXOff, RestYOff – When you sit down, your mercenary/homunculus will go nonaggressive, and if it isn't doing anything else, it will move close to you. This is the x and y offset it from the players position that it will move to. Can be positive or negative.",
"SeraCallLegionLevel": "Use this level of the Sera skill, Call Legion.",
"SeraParalyzeLevel": "Use this level of the Sera skill, Needle of Paralysis.",
"SeraPoisonMistLevel": "Use this level of the Sera skill, Poison Mist. See PoisonMistMode.",
"Snipe": "Low (TACT_SNIPE_L): Attempt to snipe this monster even while attacking other monsters, low priority",
"SpawnDelay": "After spawning, the homunculus will wait this long (in milliseconds) before trying to act. It is important to not allow the homunculus to act immediately; that can result in failure of killsteal prevention measures while teleporting.",
"StandbyFriending": "Set to 1 to use the old AzzyAI friending method.",
"SteinWandTelePause": "Time to pause after landing (from teleport or summoning) before using Stein Wand if UseSteinWandTele is enabled. Options related to Berserk Mode Through this feature, you can have the homunculus attack more aggressively in response to commands or large mobs. In the case of responses to commands, it will leave berserk mode upon killing the target.",
"StickyStandby": "If set to 1, when homunculus defends owner while in standby, it will return to standby afterwards. If set to 2, this will be remembered even if the owner teleports or relogs. Recommend setting to 1 or 2 when DefendStandby is in use.",
"SuperPassive": "If set to true (1), the homunculus will never fight another monster unless directly commanded to. DoNotChase – If set to true (1), the homunculus will never move to attack a monster. It will still engage monsters at range if it has access to a ranged attack and is configured to use it.",
"TankMonsterLimit": "Set this to the maximum number of monsters that the homunculus should attempt to tank for another killer using the TACT_TANK tactic. AutoDetectPlant (mercenary only)– When this is set to 1, the mercenary will assume that all monsters that it has not seen move or attack are plants/mushrooms, and should be treated differently (ignored, by default, see Tactics). This setting should be set to 0 if…",
"UseAttackSkill": "Set this to 1 to enable automatic use of offensive skills.",
"UseAutoHeal": "Set this to 1 to enable automatic use of healing skills (chaotic blessing or healing hands). Set this to 2 to enable automatic use of healing skills, but only when idle (including the time between killing one target and selecting the next). Set this to 3 to enable use of healing skills only when otherwise idle if there’s nothing else to do. This works only with Lif and Vanilmirth based homunculi.",
"UseAutoPushback": "Set this to 1 to enable automatic use of pushback skills to get monsters off of the mercenary. This is subject to override by the tactics list, but must be enabled here to use. This is most useful for archer mercenaries, particularly the level 6 one (with skid trap). Mercenary only.",
"UseAvoid": "homunculus only. When this is set to 1, whenever the homunculus sees a monster of a type listed in H_Avoid.lua, it will forcibly exit the RO client. H_Avoid.lua comes populated with all MVPs that can be summoned from Bloody Branches, as well as several nasty DB monsters. You may customize it by following the examples in H_Avoid.lua. It is recommended to test this before relying on it, because on…",
"UseBayeriAngriffModus": "This controls use of the Bayeri skill Angriff Modus.",
"UseBayeriGoldenFerse": "This controls use of the Bayeri skill Golden Ferse.",
"UseBayeriHailageStar": "If set to 1, enable use of the Bayeri skill, Hailage Star.",
"UseBayeriStahlHorn": "If set to 1, enable use of the Bayeri skill, Stahl Horn.",
"UseBayeriSteinWand": "Enable this option to use the Bayeri skill Stein Wand (“Stone Wall”) when a sufficiently large mob is attacking the owner or homunculus.",
"UseBerserkMobbed": "Set to 0 to disable, otherwise, when fighting this many or more monsters at once (total of monsters on homunculus and friends/owner), homunculus will go into berserk mode until there are fewer than this many monsters.",
"UseBerzerkAttack": "Set to 1 to enter berserk mode when commanded to attack.",
"UseBerzerkSkill": "Set to 1 to enter berserk mode when commanded to use an offensive skill.",
"UseBlessingOwner": "This controls use of the GM Support Mercenary skill Blessing on the owner.",
"UseBlessingSelf": "This controls use of the GM Support Mercenary skill Blessing on the mercenary.",
"UseCastleDefend": "For an Amistr, enable this to use Castling if the owner is being attacked by enough monsters, and the Amistr is being attacked by fewer monsters than the owner.",
"UseCastleRoute": "For an Amistr, enable this to use Castling to walk the owner along a route; see Route Walk under advanced options.",
"UseDanceAttack": "If set to 1, when homunculus is attacking with normal attacks, it will “dance” to increase it’s effective attack speed. homunculus only (dancing no longer increases the attack speed of mercenaries). Note that dancing prevents the homunculus from regenerating SP while fighting monsters – if your homunculus has an active attack skill, you are likely better off NOT using dance attack.",
"UseDefensiveBuff": "This controls use of defensive self-buff skills, if it has one: • Amistr Bulwark • Accelerated Flight • Guard • Parrying • Urgent Escape UseAutoSight (mercenary only) – This controls use of Sight. UseAutoMag (mercenary only) – This controls use of Magnificat.",
"UseDieterGraniticArmor": "This controls use of the Dieter skill Granitic Armor.",
"UseDieterLavaSlide": "If set to 1, enable use of the Dieter skill, Lava Slide. See LavaSlideMode.",
"UseDieterMagmaFlow": "This controls use of the Dieter skill Magma Flow.",
"UseDieterPyroclastic": "This controls use of the Dieter skill Pyroclastic.",
"UseDieterVolcanicAsh": "If set to 1, enable use of the Dieter skill, Volcanic Ash, as a debuff skill.",
"UseEiraEraseCutter": "If set to 1, enable use of the Eira skill, Erase Cutter.",
"UseEiraOveredBoost": "This controls use of the Eira skill Overed Boost.",
"UseEiraXenoSlasher": "If set to 1, enable use of the Eira skill, Xeno Slasher.",
"UseEleanorSonicClaw": "If set to 1, enable use of the Eleanor skill, Sonic Claw.",
"UseEleanorTinderBreaker": "If set to 1, enable use of the Eleanor skill, Tinder Breaker.",
"UseHomunSSkillAttack": "Set to 1 (default) to use the homunculus S single target attack skills while attacking. The purpose of these two options is to give players a way to disable the skills while attacking or chasing. For example, many of the homunculus S skills have interruptible cast times – if you’re on a map with monsters that your homunculus cannot flee, you probably do not want to use these skills while…",
"UseHomunSSkillChase": "Set to 1 (default) to use the homunculus S single target attack skills while chasing",
"UseIdleWalk": "Set this to a value other than 0 to enable walking motions while idle and when HP and SP are over AggroHP/SP, and SP is IdleWalkSP. The options are: 1. Circle, around owner. 2. Cross, around owner. 3. Square, around owner. 4. Random 5. Route – Linear (see Route Walk in advanced options) 6. Route – Circular (see Route Walk in advanced options)",
"UseIncAgiOwner": "This controls use of the GM Support Mercenary skill Increase Agility on the owner. UseIncAgiSelf – This controls use of the GM Support Mercenary skill Increase Agility on the mercenary.",
"UseKyrieOwner": "This controls use of the GM Support Mercenary skill Kyrie Eleison on the owner.",
"UseKyrieSelf": "This controls use of the GM Support Mercenary skill Kyrie Eleison on the mercenary.",
"UseOffensiveBuff": "This controls use of offensive self-buff skills: • Flitting • Mental Charge • Weapon Quicken • Bloodlust",
"UseSacrificeOwner": "This controls use of Sacrifice on the owner. This only works if the mercenary is within 10 levels of the player, and the skill behaves inconsistently due to game bugs – under certain conditions which remain unclear, it is possible for the mercenary to enter a state where it is never able to cast Sacrifice, as if Sacrifice is still up, even though it is not. Mercenary only.",
"UseSeraCallLegion": "If set to 1, enable use of the Sera skill, Call Legion. See TACT_SKILLCLASS.",
"UseSeraPainkiller": "This controls use of the Sera skill Painkiller on the owner.",
"UseSeraParalyze": "If set to 1, enable use of the Sera skill, Needle of Paralysis.",
"UseSeraPoisonMist": "If set to 1, enable use of the Sera skill, Poison Mist. See PoisonMistMode.",
"UseSkillOnly": "Set this to Skill Only (1) to only use skills to attack. Set this to While Attacking (0) to use skills while attacking, but not while chasing a monster. Set this to Chase (-1) to use while chasing or attacking. The key difference between using while chasing+attacking vs attacking only is that if set to attacking only (1), it will not use ranged attack skills until it is within melee range. Chase…",
"UseSmartBulwark": "For an Amistr type homunculus, if this is set to 1, Amistr Bulwark will only be cast if doing so would leave the homunculus with at least 120 SP, so that it will be able to use Bloodlust if/when the cooldown ends. This will be disregarded if the homunculus has less than 160 max SP or use of bloodlust is not enabled.",
"UseSteinWandOwnerMob": "Use steinwand when there are this many monsters attacking the owner (TACT_WEIGHT applies here).",
"UseSteinWandSelfMob": "Use steinwand when there are this many monsters attacking the homunculus (TACT_WEIGHT applies here).",
"UseStienWandTele": "Use stienwand when you log in and when you land from teleport, but never any other time after a short delay. I'd suggest using this with DoNotChase, and use of Hailage Star enabled. The idea being that you teleport around, and if you see monsters, you stop teleporting, the Bayeri casts Stein Wand, and then blows the mob away with Hailage Star. This should not be used with UseBayeriSteinWand, as…"
}

# Esquema de tactics (13 campos del tuple MyTact)
TACT_FIELDS = [
    ("basic", "Basic Behavior", "tact_basic", "select"),
    ("skill", "Attack Skills", None, "skill"),
    ("kite", "Kiting", "tact_kite", "select"),
    ("cast", "React to Casts", "tact_cast", "select"),
    ("push", "Pushback", "tact_push", "select"),
    ("debuff", "Debuff", "tact_debuff", "select"),
    ("class", "Skill Class", "tact_class", "select"),
    ("rescue", "Rescue", "tact_rescue", "select"),
    ("level", "Fixed Level", None, "num"),
    ("snipe", "Snipe", "tact_snipe", "select"),
    ("ks", "Kill-steal", "tact_ks", "select"),
    ("priority", "Priority", None, "num"),
    ("chase", "Chase", "tact_chase", "select"),
]

PVP_SPECIAL = {"KOS": 12, "ENEMY": 11, "NEUTRAL": 10, "FRIEND": 1, "ALLY": 13, "RETAINER": 2}
PVP_SPECIAL_REV = {v: k for k, v in PVP_SPECIAL.items()}

# Constantes de tactics: se resuelven leyendo Const_.lua (junto al script)
BASIC_CONSTS = ["TACT_TANKMOB", "TACT_TANK", "TACT_IGNORE", "TACT_ATTACK_L", "TACT_ATTACK_M",
                "TACT_ATTACK_H", "TACT_REACT_L", "TACT_REACT_M", "TACT_REACT_H", "TACT_REACT_SELF",
                "TACT_SNIPE_L", "TACT_SNIPE_M", "TACT_SNIPE_H", "TACT_ATK_L_REACT_M",
                "TACT_ATTACK_LAST", "TACT_ATTACK_TOP"]
FIELD_PREFIX = {"basic": BASIC_CONSTS, "skill": ["SKILL_"], "kite": ["KITE_"], "cast": ["CAST_"],
                "push": ["PUSH_"], "debuff": ["DEBUFF_"], "class": ["CLASS_"],
                "rescue": ["RESCUE_"], "snipe": ["SNIPE_"], "ks": ["KS_"], "chase": ["CHASE_"]}

def load_constants(user_ai):
    """Parsea Const_.lua: dict con nombre de constante y valor."""
    consts = {}
    cpath = os.path.join(user_ai, "Const_.lua")
    if os.path.isfile(cpath):
        with open(cpath, encoding="utf-8", errors="replace") as f:
            for m in re.finditer(r"(?m)^\s*([A-Z][A-Z0-9_]+)\s*=\s*(-?\d+\.?\d*)", f.read()):
                consts[m.group(1)] = float(m.group(2))
    return consts

_CONSTS_CACHE = {}

def tact_token(v, fid, user_ai):
    """Convierte el valor a su nombre de constante si existe (ej: 3 -> TACT_ATTACK_M)."""
    if v is None:
        v = 0
    consts = _CONSTS_CACHE.get(user_ai)
    if consts is None:
        consts = _CONSTS_CACHE[user_ai] = load_constants(user_ai)
    prefs = FIELD_PREFIX.get(fid, [])
    for pref in prefs:
        if isinstance(pref, list):
            for name in pref:
                if consts.get(name) == v:
                    return name
        else:
            for name, val in consts.items():
                if name.startswith(pref) and val == v:
                    return name
    return fmt_num(v)

# ----------------------------------------------------------------------------
# Parser / escritor de Lua
# ----------------------------------------------------------------------------

NUM_RE = r"(-?(?:\d+\.?\d*|\.\d+))"
CFG_RE = re.compile(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*" + NUM_RE)
TACT_RE = re.compile(r"(?m)^(My(?:PVP)?Tact)\[(\w+)\]\s*=\s*\{([^}]*)\}\s*(?:--\s*(.*))?$")
DATE_RE = re.compile(r'(LastSavedDate\s*=\s*)"[^"]*"')

def read_config(path):
    """Devuelve dict {opcion: valor(float|None)} presente en el archivo."""
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for m in CFG_RE.finditer(f.read()):
            try:
                out[m.group(1)] = float(m.group(2))
            except ValueError:
                pass
    return out

def write_config(path, updates):
    """Actualiza valores in-place con regex (como el exe original).
    Añade al final las opciones que no existan. Devuelve lista de cambios."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    added = []
    for name, value in updates.items():
        if value is None or value != value:
            raise ValueError("Valor no numérico para '" + name + "'")
        val = fmt_num(value)
        pat = re.compile(r"(?m)^(\s*" + re.escape(name) + r"\s*=\s*)" + NUM_RE)
        new_text, n = pat.subn(lambda mm: mm.group(1) + val, text)
        if n == 0:
            added.append(name)
        else:
            text = new_text
    if added:
        block = "".join("\n{:<25}= {}".format(n, fmt_num(updates[n])) for n in added)
        text = text.rstrip("\n") + "\n" + block + "\n"
    text = DATE_RE.sub(r'\1"ConfigX {}"'.format(datetime.now().strftime("%Y-%m-%d %H:%M")), text, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return added

def fmt_num(v):
    if v is None:
        return "0"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)

def read_tactics(path, table):
    """Parsea MyTact[ID]={...} --Name → lista de dicts."""
    entries = []
    if not os.path.isfile(path):
        return entries
    with open(path, encoding="utf-8", errors="replace") as f:
        for m in TACT_RE.finditer(f.read()):
            if m.group(1) != table:
                continue
            key = m.group(2)
            raw = [x.strip() for x in m.group(3).split(",")]
            consts = load_constants(os.path.dirname(path))
            vals = []
            for x in raw:
                try:
                    vals.append(float(x))
                except ValueError:
                    vals.append(consts.get(x, x))
            e = {"key": key, "name": (m.group(4) or "").strip()}
            for i, (fid, _lbl, _en, _w) in enumerate(TACT_FIELDS):
                e[fid] = vals[i] if i < len(vals) else (-1 if fid == "level" else 0)
            entries.append(e)
    return entries

def _validate_tacts(entries, allow_special, label):
    """Valida keys (numéricas o constantes PVP) y valores antes de escribir."""
    seen = set()
    for e in entries:
        k = str(e.get("key", "")).strip()
        if not k.isdigit() and not (allow_special and k in PVP_SPECIAL):
            raise ValueError("{}: key inválida '{}' — debe ser ID numérico{}".format(
                label, k, " o KOS/ENEMY/NEUTRAL/FRIEND/ALLY/RETAINER" if allow_special else ""))
        if k in seen:
            raise ValueError("{}: key duplicada {}".format(label, k))
        seen.add(k)
        for fid, _lbl, _en, _w in TACT_FIELDS:
            v = e.get(fid)
            if fid not in ("key", "name") and (v is None or v != v):
                raise ValueError("{}: valor inválido en '{}' de la key {}".format(label, fid, k))


def write_tactics(path, table, entries, extra_default_line=True):
    """Reescribe la sección de tactics conservando el resto del archivo."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    ua_dir = os.path.dirname(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    # elimina líneas existentes de la tabla
    text = re.sub(r"(?m)^" + table + r"\[[^\n]*\n?", "", text)
    # asegura MyTact={} al inicio
    header = table + "={}\n"
    if not re.search(r"(?m)^" + table + r"\s*=\s*\{\}", text):
        text = header + text
    lines = [header.rstrip("\n")]
    def _sk(e):
        s = str(e["key"])
        try:
            return (0, int(s), "")
        except ValueError:
            return (1, 0, s)
    for e in sorted(entries, key=_sk):
        vals = []
        fields_to_write = TACT_FIELDS[:8] if table == "MyPVPTact" else TACT_FIELDS
        for fid, _lbl, _en, _w in fields_to_write:
            v = e[fid]
            if fid in ("level", "priority"):
                vals.append(fmt_num(v) if v is not None else "-1")
            else:
                vals.append(tact_token(v, fid, ua_dir))
        name = e.get("name") or ""
        lines.append("{}[{}]={{ {} }}{}".format(
            table, e["key"], ", ".join(vals), (" --" + name) if name else ""))
    block = "\n".join(lines) + "\n"
    # inserta el bloque justo después del header existente
    text = re.sub(r"(?m)^" + table + r"\s*=\s*\{\}[^\n]*\n", "", text)
    text = block + text.lstrip("\n")
    m = re.search(r"TactLastSavedDate\s*=\s*\"[^\"]*\"", text)
    if m:
        text = text.replace(m.group(0),
            'TactLastSavedDate        = "ConfigX {}"'.format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def read_text(path):
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()

# ----------------------------------------------------------------------------
# Estado de la app
# ----------------------------------------------------------------------------

class ConfigX:
    def __init__(self, ai_dir=None):
        self.ai_dir = ai_dir or os.path.join(script_dir(), "..", "..")  # USER_AI/../.. no: USER_AI está en AI/
        # el script vive en AI/USER_AI → la raíz del juego es ../..
        cand = os.path.abspath(ai_dir) if ai_dir else os.path.abspath(os.path.join(script_dir(), "..", ".."))
        self.ai_dir = cand
        self.user_ai = script_dir()
        self.files = {
            "hom": os.path.join(self.user_ai, "H_Config.lua"),
            "mer": os.path.join(self.user_ai, "M_Config.lua"),
            "homTact": os.path.join(self.user_ai, "H_Tactics.lua"),
            "merTact": os.path.join(self.user_ai, "M_Tactics.lua"),
            "pvp": os.path.join(self.user_ai, "H_PVP_Tact.lua"),
            "merPvp": os.path.join(self.user_ai, "M_PVP_Tact.lua"),
            "extraH": os.path.join(self.user_ai, "H_Extra.lua"),
            "extraM": os.path.join(self.user_ai, "M_Extra.lua"),
        }
        for k, p in self.files.items():
            if not os.path.isfile(p):
                print("AVISO: no se encontró " + p)

    def defaults(self):
        dpath = os.path.join(self.user_ai, "Defaults.lua")
        return read_config(dpath) if os.path.isfile(dpath) else {}

    def state(self):
        defs = self.defaults()
        hom_vals = read_config(self.files["hom"])
        mer_vals = read_config(self.files["mer"])
        hom_meta = [{"name": n, "cat": c, "enum": e, "tip": TIPS.get(n, "")}
                    for (n, c, e) in _HOM]
        # opciones del mercenario: todas las presentes en el archivo + metadata conocida
        mer_meta = []
        seen = set()
        for n in mer_vals:
            if n in seen or n in ("LastSavedDate", "TactLastSavedDate"):
                continue
            seen.add(n)
            cat, en = _MER_META.get(n, ("Other", None))
            mer_meta.append({"name": n, "cat": cat, "enum": en, "tip": TIPS.get(n, "")})
        return {
            "files": {k: os.path.relpath(p, self.ai_dir) for k, p in self.files.items()},
            "enums": {k: [[v, l] for (v, l) in vals] for k, vals in ENUMS.items()},
            "homMeta": hom_meta, "merMeta": mer_meta,
            "hom": hom_vals, "mer": mer_vals, "defaults": defs,
            "homTact": read_tactics(self.files["homTact"], "MyTact"),
            "merTact": read_tactics(self.files["merTact"], "MyTact"),
            "pvp": read_tactics(self.files["pvp"], "MyPVPTact"),
            "merPvp": read_tactics(self.files["merPvp"], "MyPVPTact"),
            "extraH": read_text(self.files["extraH"]),
            "extraM": read_text(self.files["extraM"]),
            "pvpSpecial": PVP_SPECIAL,
        }

    def apply(self, payload):
        log = []
        if "hom" in payload:
            added = write_config(self.files["hom"], payload["hom"])
            log.append("H_Config.lua: {} opciones actualizadas".format(len(payload["hom"])) +
                       (" (añadidas: " + ", ".join(added) + ")" if added else ""))
        if "mer" in payload:
            added = write_config(self.files["mer"], payload["mer"])
            log.append("M_Config.lua: {} opciones actualizadas".format(len(payload["mer"])) +
                       (" (añadidas: " + ", ".join(added) + ")" if added else ""))
        if "homTact" in payload:
            _validate_tacts(payload["homTact"], False, "H_Tactics")
            write_tactics(self.files["homTact"], "MyTact", payload["homTact"])
            log.append("H_Tactics.lua: {} entradas".format(len(payload["homTact"])))
        if "merTact" in payload:
            _validate_tacts(payload["merTact"], False, "M_Tactics")
            write_tactics(self.files["merTact"], "MyTact", payload["merTact"])
            log.append("M_Tactics.lua: {} entradas".format(len(payload["merTact"])))
        if "pvp" in payload:
            _validate_tacts(payload["pvp"], True, "H_PVP_Tact")
            write_tactics(self.files["pvp"], "MyPVPTact", payload["pvp"])
            log.append("H_PVP_Tact.lua: {} entradas".format(len(payload["pvp"])))
        if "merPvp" in payload:
            _validate_tacts(payload["merPvp"], True, "M_PVP_Tact")
            write_tactics(self.files["merPvp"], "MyPVPTact", payload["merPvp"])
            log.append("M_PVP_Tact.lua: {} entradas".format(len(payload["merPvp"])))
        if "extraH" in payload:
            with open(self.files["extraH"], "w", encoding="utf-8") as f:
                f.write(payload["extraH"])
            log.append("H_Extra.lua guardado")
        if "extraM" in payload:
            with open(self.files["extraM"], "w", encoding="utf-8") as f:
                f.write(payload["extraM"])
            log.append("M_Extra.lua guardado")
        return log

    def reset(self, which):
        defs = self.defaults()
        if which == "hom":
            opts = {n: defs.get(n, read_config(self.files["hom"]).get(n, 0)) for (n, c, e) in _HOM}
            write_config(self.files["hom"], opts)
            return "H_Config.lua restablecido a Defaults.lua"
        elif which == "mer":
            cur = read_config(self.files["mer"])
            opts = {n: defs.get(n, v) for n, v in cur.items()
                    if n not in ("LastSavedDate", "TactLastSavedDate")}
            write_config(self.files["mer"], opts)
            return "M_Config.lua restablecido (donde Defaults.lua define valor)"
        return "?"

# ----------------------------------------------------------------------------
# Servidor HTTP
# ----------------------------------------------------------------------------

HTML = '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n<title>AzzyAI Config X</title>\n<style>\n:root{\n  --bg:#12141a; --bg2:#181b24; --bg3:#1f2330; --line:#2a2f40;\n  --tx:#d7dae3; --tx2:#8b93a7; --acc:#7c5cff; --acc2:#39d98a;\n  --warn:#ffb84d; --err:#ff6b6b;\n}\n*{box-sizing:border-box}\nbody{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 "Segoe UI",system-ui,sans-serif}\nheader{display:flex;align-items:center;gap:14px;padding:10px 16px;background:var(--bg2);border-bottom:1px solid var(--line);flex-wrap:wrap}\n#topbar{position:sticky;top:0;z-index:20}\nheader h1{font-size:16px;margin:0;font-weight:600}\nheader h1 span{color:var(--acc)}\n.badge{font-size:11px;color:var(--tx2);border:1px solid var(--line);padding:2px 8px;border-radius:20px}\nheader .sp{flex:1}\nbutton{background:var(--bg3);color:var(--tx);border:1px solid var(--line);border-radius:8px;padding:7px 14px;cursor:pointer;font-size:13px}\nbutton:hover{border-color:var(--acc)}\nbutton.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}\nbutton.primary:hover{filter:brightness(1.12)}\nbutton.danger{color:var(--err)}\n#log{position:fixed;right:12px;bottom:12px;max-width:420px;background:var(--bg3);border:1px solid var(--line);border-radius:10px;padding:10px 14px;font-size:12px;display:none;box-shadow:0 6px 24px rgba(0,0,0,.5);z-index:50;white-space:pre-wrap}\n#log.ok{border-color:var(--acc2)} #log.bad{border-color:var(--err)}\nnav{display:flex;gap:2px;padding:0 12px;background:var(--bg2);border-bottom:1px solid var(--line);overflow-x:auto}\nnav a{padding:9px 14px;color:var(--tx2);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;font-size:13px}\nnav a.on{color:var(--tx);border-bottom-color:var(--acc);font-weight:600}\nmain{padding:14px;max-width:1180px;margin:0 auto}\n.search{width:260px;background:var(--bg3);border:1px solid var(--line);border-radius:8px;color:var(--tx);padding:6px 10px;font-size:13px}\n.cat{margin:14px 0 6px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--acc);border-bottom:1px solid var(--line);padding-bottom:4px}\n.opt{display:grid;grid-template-columns:250px 240px 130px 1fr;gap:8px;align-items:center;padding:5px 8px;border-radius:6px}\n.opt:hover{background:var(--bg2)}\n.opt .nm{font-weight:600}\n.opt .nm i{font-style:normal;color:var(--warn);margin-left:6px;font-size:11px}\n.opt .tip{color:var(--tx2);font-size:12px;cursor:help}\n.opt.changed{background:rgba(124,92,255,.08);outline:1px solid rgba(124,92,255,.25)}\nselect,input[type=number],input[type=text]{background:var(--bg3);color:var(--tx);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:13px;width:100%}\nselect:focus,input:focus{outline:1px solid var(--acc)}\ntable{width:100%;border-collapse:collapse;font-size:13px}\nth{position:sticky;top:0;background:var(--bg2);text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);z-index:2;font-size:12px;color:var(--tx2)}\ntd{padding:5px 8px;border-bottom:1px solid rgba(42,47,64,.4);vertical-align:middle}\ntr:hover td{background:var(--bg2)}\ntd input,td select{min-width:90px}\ntd.key input{width:80px}\n.tbar{display:flex;gap:10px;align-items:center;margin:8px 0}\n.note{color:var(--tx2);font-size:12px;margin:6px 0}\ntextarea{width:100%;height:440px;background:var(--bg2);color:#cdd3e0;border:1px solid var(--line);border-radius:10px;padding:12px;font:12px/1.5 ui-monospace,Consolas,monospace;resize:vertical}\n.tabsExtra{display:flex;gap:10px;margin-bottom:8px}\n.pvpname{min-width:140px!important}\n@media(max-width:900px){.opt{grid-template-columns:1fr 1fr}.opt .tip{display:none}}\n</style>\n</head>\n<body>\n<div id="topbar">\n<header>\n  <h1>AzzyAI <span>Config X</span></h1>\n  <span class="badge" id="verBadge"></span>\n  <span class="badge" id="dirBadge"></span>\n  <div class="sp"></div>\n  <button onclick="resetCfg(\'hom\')" title="Restablecer homúnculo a Defaults.lua">↺ Reset Hom</button>\n  <button onclick="resetCfg(\'mer\')" title="Restablecer mercenario donde Defaults.lua define valor">↺ Reset Mer</button>\n  <button onclick="revert()">Revertir</button>\n  <button onclick="impFile.click()" title="Importar un .lua de configuración (como File > Import del original)">Importar…</button>\n  <input type="file" id="impFile" accept=".lua" style="display:none" onchange="importFile(this)">\n  <button class="primary" onclick="applyAll()">✓ Apply</button>\n</header>\n<nav id="tabs">\n  <a data-t="hom" class="on">Homunculus</a>\n  <a data-t="mer">Mercenary</a>\n  <a data-t="homTact">Homunculus Tactics</a>\n  <a data-t="merTact">Mercenary Tactics</a>\n  <a data-t="pvp">PVP Tactics</a>\n  <a data-t="merPvp">Merc PVP Tactics</a>\n  <a data-t="extra">Extra Options</a>\n</nav>\n</div>\n<main id="content"><div class="note">Cargando…</div></main>\n<div id="log"></div>\n<script>\nlet S=null, cur="hom", dirty={};\n\nfunction $(s,r){return (r||document).querySelector(s)}\nfunction $$(s,r){return [...(r||document).querySelectorAll(s)]}\nconst esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;"}[c]));\n\nasync function api(p,d){\n  const r=await fetch("/api/"+p,{method:d?"POST":"GET",headers:{"Content-Type":"application/json"},body:d?JSON.stringify(d):undefined});\n  const j=await r.json();\n  if(!r.ok) throw new Error(j.error||r.status);\n  return j;\n}\nfunction toast(msg,ok){\n  const el=$("#log");\n  el.textContent=msg; el.className=ok===false?"bad":"ok"; el.style.display="block";\n  clearTimeout(el._t); el._t=setTimeout(()=>el.style.display="none", ok===false?8000:3500);\n}\n\n$$("nav a").forEach(a=>a.onclick=()=>{\n  $$("nav a").forEach(x=>x.classList.remove("on")); a.classList.add("on");\n  cur=a.dataset.t; render();\n});\n\nasync function load(){\n  S=await api("state");\n  $("#verBadge").textContent="AzzyAI "+ (S.hom.PVPmode!==undefined?"v1.56":"");\n  $("#dirBadge").textContent=S.files.hom.replace("AI/USER_AI/","");\n  dirty={};\n  render();\n}\nasync function revert(){ S=(await api("reload")).state; dirty={}; render(); toast("Recargado desde disco."); }\n\nfunction enumSel(name,v,enumName){\n  const opts=S.enums[enumName]||[];\n  let h=`<select onchange="setVal(\'${name}\',this.value)">`;\n  for(const [val,lab] of opts) h+=`<option value="${val}" ${String(val)===String(v)?"selected":""}>${esc(lab)}</option>`;\n  const known=opts.some(([val])=>String(val)===String(v));\n  if(!known&&v!==undefined) h+=`<option value="${v}" selected>${v} (valor crudo)</option>`;\n  h+="</select>";\n  return h;\n}\n\nfunction setVal(name,val){\n  const v=parseFloat(val);\n  if(isNaN(v)){ toast("Valor inválido: se ignora el cambio",false); return; }\n  S[cur][name]=v;\n  const tgt=dirty[cur]||(dirty[cur]={});\n  tgt[name]=v;\n  const row=document.querySelector(\'.opt[data-name="\'+name+\'"]\');\n  if(row){\n    const dv=S.defaults[name];\n    const changed=dv!==undefined&&String(dv)!==String(v);\n    row.classList.toggle("changed",changed);\n    row.querySelector(".nm").innerHTML=esc(name)+(changed?"<i>≠def</i>":"");\n    const t=row.querySelector(".tip");\n    if(t) t.textContent="default: "+(dv!==undefined?dv:"—");\n  }\n}\n\nfunction render(){\n  const c=$("#content");\n  const sc=window.scrollY;\n  if(cur==="hom"||cur==="mer"){\n    const meta=cur==="hom"?S.homMeta:S.merMeta;\n    const vals=cur==="hom"?S.hom:S.mer;\n    const q=($("#q")?.value||"").toLowerCase();\n    const cats={};\n    meta.filter(m=>!q||m.name.toLowerCase().includes(q)||(m.tip||"").toLowerCase().includes(q)).forEach(m=>{\n      (cats[m.cat]=cats[m.cat]||[]).push(m);\n    });\n    let h=`<input class="search" id="q" placeholder="Buscar opción…" value="${esc($("#q")?.value||"")}" oninput="render()">`;\n    h+=`<div class="note">Amarillo = difiere de Defaults.lua. Se guarda con <b>Apply</b> (regex in-place, como el original).</div>`;\n    for(const cat of Object.keys(cats).sort()){\n      h+=`<div class="cat">${esc(cat)} (${cats[cat].length})</div>`;\n      for(const m of cats[cat]){\n        const v=vals[m.name];\n        const dv=S.defaults[m.name];\n        const changed=dv!==undefined&&String(dv)!==String(v);\n        const fld=m.enum?enumSel(m.name,v,m.enum)\n          :`<input type="number" step="any" value="${v??0}" onchange="setVal(\'${m.name}\',this.value)">`;\n        h+=`<div class="opt ${changed?"changed":""}" data-name="${esc(m.name)}" title="${esc(m.tip||"")}">\n          <div class="nm">${esc(m.name)}${changed?"<i>≠def</i>":""}</div>\n          <div>${fld}</div>\n          <div class="tip">default: ${dv!==undefined?dv:"—"}</div>\n          <div class="tip">${esc((m.tip||"").slice(0,150))}</div></div>`;\n      }\n    }\n    c.innerHTML=h;\n    const qi=$("#q"); const pos=qi.value.length; qi.focus(); qi.setSelectionRange(pos,pos);\n  }\n  else if(cur==="homTact"||cur==="merTact"){ c.innerHTML=tactTable(cur==="homTact"?"homTact":"merTact","MyTact",true); }\n  else if(cur==="pvp"||cur==="merPvp"){ c.innerHTML=tactTable(cur,false,false); }\n  else{ c.innerHTML=extraTab(); }\n  window.scrollTo(0,sc);\n}\n\nfunction tactTable(key,isMon){\n  const list=S[key];\n  const fields=isMon?TACT_F: TACT_F.slice(0,8);\n  let h=`<div class="tbar">\n    <button class="primary" onclick="addRow(\'${key}\',${isMon})">+ Añadir</button>\n    <span class="note">${isMon?"Key = ID de monstruo (solo números). El nombre es solo comentario.":"Key = ID de jugador (número) o constante: KOS/ENEMY/NEUTRAL/FRIEND/ALLY/RETAINER."}</span></div>\n    <div style="overflow:auto;max-height:78vh"><table><thead><tr>\n    <th>Key</th><th>Nombre</th>`;\n  for(const f of fields) h+=`<th${f[0]==="skill"?\' title="0=Never · 100=Always · N=usar N veces · negativo=ese nivel solo 1 vez"\':""}>${esc(f[1])}</th>`;\n  h+=`<th></th></tr></thead><tbody>`;\n  for(let i=0;i<list.length;i++){\n    const e=list[i];\n    h+=`<tr><td class="key"><input type="text" value="${esc(e.key)}" onchange="editTact(\'${key}\',${i},\'key\',this.value)"></td>\n        <td class="pvpname"><input type="text" value="${esc(e.name)}" onchange="editTact(\'${key}\',${i},\'name\',this.value)"></td>`;\n    for(const [fid,lbl,en,w] of fields){\n      if(en) h+=`<td>${tactEnumSel(key,i,fid,e[fid],en)}</td>`;\n      else h+=`<td><input type="number" step="any" value="${e[fid]??-1}" onchange="editTact(\'${key}\',${i},\'${fid}\',this.value)"></td>`;\n    }\n    h+=`<td><button class="danger" onclick="delRow(\'${key}\',${i})">✕</button></td></tr>`;\n  }\n  h+="</tbody></table></div>";\n  return h;\n}\nfunction tactEnumSel(key,i,fid,v,en){\n  let h=`<select onchange="editTact(\'${key}\',${i},\'${fid}\',this.value)">`;\n  for(const [val,lab] of (S.enums[en]||[])) h+=`<option value="${val}" ${String(val)===String(v)?"selected":""}>${esc(lab)}</option>`;\n  const known=(S.enums[en]||[]).some(([val])=>String(val)===String(v));\n  if(!known) h+=`<option value="${v}" selected>${v}</option>`;\n  return h+"</select>";\n}\nfunction editTact(key,i,fid,val){\n  if(fid==="key"||fid==="name"){ S[key][i][fid]=val; }\n  else{\n    const v=parseFloat(val);\n    if(isNaN(v)){ toast("Valor inválido",false); return; }\n    S[key][i][fid]=v;\n  }\n  dirty[key]=S[key];\n}\nfunction addRow(key,isMon){\n  const def={key:"0",name:"Nuevo",basic:3,skill:100,kite:1,cast:1,push:0,debuff:0,class:-1,rescue:0,level:-1,snipe:1,ks:0,priority:1,chase:-1};\n  S[key].push(def); dirty[key]=S[key]; render();\n}\nfunction delRow(key,i){ S[key].splice(i,1); dirty[key]=S[key]; render(); }\n\nfunction extraTab(){\n  return `<div class="tabsExtra">\n   <button class="primary" onclick="saveExtra()">✓ Guardar ambos</button>\n   <a href="/api/export/extraH"><button>⤓ H_Extra.lua</button></a>\n   <a href="/api/export/extraM"><button>⤓ M_Extra.lua</button></a></div>\n   <div class="note">Aquí puedes modificar configuraciones no soportadas por el GUI (igual que la pestaña "Extra Options" del original).</div>\n   <b>H_Extra.lua (homúnculo)</b>\n   <textarea id="exH">${esc(S.extraH)}</textarea>\n   <b>M_Extra.lua (mercenario)</b>\n   <textarea id="exM">${esc(S.extraM)}</textarea>`;\n}\nasync function saveExtra(){\n  const exH=$("#exH").value, exM=$("#exM").value;\n  const r=await api("apply",{extraH:exH,extraM:exM});\n  toast("Extra guardado:\\n"+r.log.join("\\n"));\n  S.extraH=exH; S.extraM=exM;\n}\n\nconst FILEMAP={"H_Config.lua":"hom","M_Config.lua":"mer","H_Tactics.lua":"homTact","M_Tactics.lua":"merTact","H_PVP_Tact.lua":"pvp","M_PVP_Tact.lua":"merPvp","H_Extra.lua":"extraH","M_Extra.lua":"extraM"};\nfunction importFile(inp){\n  const f=inp.files&&inp.files[0]; if(!f) return;\n  const key=FILEMAP[f.name];\n  if(!key){ toast("Archivo no reconocido: "+f.name+" (debe llamarse como los .lua de USER_AI)",false); inp.value=""; return; }\n  f.text().then(t=>api("import",{key,text:t})).then(async r=>{\n    toast(r.msg+" — recargando…");\n    S=await api("state"); dirty={}; render();\n  }).catch(e=>toast("Error importando: "+e.message,false));\n  inp.value="";\n}\n\nasync function applyAll(){\n  const payload={};\n  if(dirty.hom) payload.hom=dirty.hom;\n  if(dirty.mer) payload.mer=dirty.mer;\n  for(const k of ["homTact","merTact","pvp","merPvp"]) if(dirty[k]) payload[k]=dirty[k];\n  const exH=$("#exH"),exM=$("#exM");\n  if(exH&&exH.value!==S.extraH) payload.extraH=exH.value;\n  if(exM&&exM.value!==S.extraM) payload.extraM=exM.value;\n  if(!Object.keys(payload).length){ toast("No hay cambios pendientes."); return; }\n  try{\n    const r=await api("apply",payload);\n    toast("Guardado:\\n"+r.log.join("\\n"));\n    dirty={};\n    S=(await api("reload")).state; render();\n  }catch(e){ toast("Error: "+e.message,false); }\n}\nasync function resetCfg(w){\n  if(!confirm("¿Restablecer la configuración de "+(w==="hom"?"homúnculo":"mercenario")+"?"))return;\n  const r=await api("reset",{which:w});\n  toast(r.msg); S=r.state; dirty={}; render();\n}\nconst TACT_F=[["basic","Basic","tact_basic"],["skill","Skills",null],["kite","Kite","tact_kite"],\n["cast","Cast","tact_cast"],["push","Push","tact_push"],["debuff","Debuff","tact_debuff"],\n["class","Class","tact_class"],["rescue","Rescue","tact_rescue"],["level","Level",null],\n["snipe","Snipe","tact_snipe"],["ks","KS","tact_ks"],["priority","Prio",null],["chase","Chase","tact_chase"]];\n\nload().catch(e=>{document.getElementById("content").innerHTML=\'<div class="note">Error: \'+esc(e.message)+\'</div>\'});\n</script>\n</body>\n</html>\n'

class Handler(http.server.BaseHTTPRequestHandler):
    app = None  # type: ConfigX

    def log_message(self, fmt, *args):
        print("[req] " + fmt % args, flush=True)

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            data = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p == "/api/state":
            self._json(self.app.state())
        elif p == "/api/reload":
            self._json({"ok": True, "state": self.app.state()})
        elif p.startswith("/api/export/"):
            key = p.split("/")[-1]
            path = self.app.files.get(key)
            if path and os.path.isfile(path):
                with open(path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition",
                                 'attachment; filename="' + os.path.basename(path) + '"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._json({"error": "archivo no encontrado"}, 404)
        else:
            self._json({"error": "no encontrado"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception as e:
            return self._json({"error": "JSON inválido: " + str(e)}, 400)
        try:
            if p == "/api/apply":
                log = self.app.apply(payload)
                return self._json({"ok": True, "log": log})
            if p == "/api/reload":
                return self._json({"ok": True, "state": self.app.state()})
            if p == "/api/reset":
                msg = self.app.reset(payload.get("which", ""))
                return self._json({"ok": True, "msg": msg, "state": self.app.state()})
            if p == "/api/import":
                key = payload.get("key")
                text = payload.get("text", "")
                if key in self.app.files and text:
                    with open(self.app.files[key], "w", encoding="utf-8") as f:
                        f.write(text)
                    return self._json({"ok": True, "msg": "importado " + key})
                return self._json({"error": "clave inválida"}, 400)
        except Exception as e:
            return self._json({"error": str(e)}, 500)
        self._json({"error": "no encontrado"}, 404)


def free_port(preferred=7317):
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                port = s.getsockname()[1]
                return port
            except OSError:
                continue
    return 0


def open_browser(url):
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", urlparse(url).port), timeout=0.3):
                break
        except OSError:
            time.sleep(0.2)
    webbrowser.open(url)


def main():
    args = sys.argv[1:]
    ai_dir = None
    port = 7317
    no_browser = "--no-browser" in args
    if "--ai-dir" in args:
        ai_dir = args[args.index("--ai-dir") + 1]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    Handler.app = ConfigX(ai_dir)
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    url = "http://127.0.0.1:{}/".format(port)
    print("=" * 62, flush=True)
    print(" AzzyAI Config X — reconstrucción multiplataforma del config tool", flush=True)
    print(" Archivos: " + Handler.app.user_ai, flush=True)
    print(" Interfaz: " + url, flush=True)
    print(" Cierra con Ctrl+C", flush=True)
    print("=" * 62, flush=True)
    if not no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nHasta luego.")

if __name__ == "__main__":
    main()
