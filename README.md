# AzzyAI-Fork for kRO Homunculus Update

This is not the official AzzyAI but a fork.
For the original repository please refer to: https://github.com/SpenceKonde/AzzyAI

For more information, see the official website: http://drazzy.com/ro/ai

## Versions
Currently, there are two versions of this AI:
### [Main](https://github.com/Kisaro/AzzyAI/archive/master.zip)
This branch attempts to be close to vanilla azzyai without further modifications except introducing the skill-changes below. **Pick this version if you want to be as close to vanilla azzyai as possible and like tinkering with the settings.**
### [Custom](https://github.com/Kisaro/AzzyAI/archive/custom-settings.zip)
Contains everything above, plus some personal adjustments to auto-cast some skills and modifications to cooldowns to aim for 100% uptime of various buffs. **Pick this version if you want an AI tailored to Amistr+Dieter out of the box.**

## Install ##
 - Download a version ([main](https://github.com/Kisaro/AzzyAI/archive/master.zip) or [custom](https://github.com/Kisaro/AzzyAI/archive/custom-settings.zip)) of your choice from above
 - Open the downloaded ZIP-file
 - Navigate to your Ragnarok-folder
 - Copy the *USER_AI*-folder from the ZIP-file into the *AI*-folder of your Ragnarok-folder (will overwrite the currently installed user-AI, make backups!)
 - To instantly see changes ingame, *Rest* -> *Call* your Homunculus or use `@refresh` if you have access to server commands

## Changes ##
Skills are updated to their new max-level to reflect [official kRO changes](http://ro.gnjoy.com/news/notice/View.asp?BBSMode=10001&seq=6843&curpage=1)

This includes the following skills:
 - Eira
   - Xeno Slasher
   - Eraser Cutter
 - Bayeri
   - Stahl Horn
   - Heilige Stange
 - Sera
   - Needle of Paralyze
   - Pain Killer
 - Dieter
   - Lava Slide
   - Pyroclastic
 - Eleanor
   - Silvervein Rush
   - Midnight Frenzy

Addionally, with the arrival of 4th jobs and new homunculus skills, the following new skills have been added:
 - Dieter
   - Tempering
   - Blast Forge (Thanks to [vorpal1337](https://github.com/vorpal1337))
   
## AzzyAI Config X (cross-platform configuration tool)
The bundled `AzzyAIConfig.exe` is Windows-only (.NET Framework 4.0 WinForms). `USER_AI/azzyai-configx.py` is a fully cross-platform reconstruction of its UI — it runs on Linux, Windows and macOS with plain Python 3 (standard library only, zero dependencies):

- The same 7 tabs: Homunculus, Mercenary, Homunculus Tactics, Mercenary Tactics, PVP Tactics, Merc PVP Tactics, Extra Options
- Every option found in `H_Config.lua` / `M_Config.lua`, grouped by the original's categories, with enum dropdowns and defaults from `Defaults.lua`
- Tactics editors that read and write the real `TACT_*` / `SKILL_*` / `CLASS_*` constants (parsed from `Const_.lua`)
- In-place regex saves: file comments and layout are preserved, exactly like the original tool
- Improvements over the original: live option search, tooltips extracted from `Documentation.pdf`, "differs from default" highlighting, NaN/invalid input guards and duplicate/invalid tactics-key validation, plus an E2E test suite

Usage: copy it into your `USER_AI` folder and run `python3 azzyai-configx.py` — the interface opens in your browser automatically. Rest -> Call your homunculus (or `@refresh`) for changes to take effect.

## Disclaimer ##
Certain functionality may not work as expected or not at all due to the declining support of AIs in newer clients, backup your current AI in any case before applying. Feel free to open issues if you find bugs. **Pull-requests are welcome!**
