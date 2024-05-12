"""
Containts constats and globals that are accessed frequently in all modules
"""
import pathlib

import xml_helper
import text_helper

PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_DIR / 'data'
GAME_DATA_DIR = DATA_DIR / 'GameData'

DPS_FORMULA = ('{dps_bonus_mult}*({dps_bonus_add}+{targets}*{wpn_bonus_mult}*'
               '(({min}+{max})/2+{wpn_bonus_add})/({period}/{wpn_period_mult}))')

LIFE_FORMULA = '{life_bonus_mult}*({hp}+{shields}+{life_bonus_add})'

gGameStrings = text_helper.load_text_file(DATA_DIR / 'enUS.SC2Data/LocalizedData' / 'GameStrings.txt')

gUnits = xml_helper.load_xml(GAME_DATA_DIR / 'UnitData.xml')
gWeapons = xml_helper.load_xml(GAME_DATA_DIR / 'WeaponData.xml')
gEffects = xml_helper.load_xml(GAME_DATA_DIR / 'EffectData.xml')
gUserData = xml_helper.load_xml(GAME_DATA_DIR / 'UserData.xml')
gAbils = xml_helper.load_xml(GAME_DATA_DIR / 'AbilData.xml')
gBehaviors = xml_helper.load_xml(GAME_DATA_DIR / 'BehaviorData.xml')
gValidators = xml_helper.load_xml(GAME_DATA_DIR / 'ValidatorData.xml')
gAccumulators = xml_helper.load_xml(GAME_DATA_DIR / 'AccumulatorData.xml')
gButtons = xml_helper.load_xml(GAME_DATA_DIR / 'ButtonData.xml')
gActors = xml_helper.load_xml(GAME_DATA_DIR / 'ActorData.xml')
gUpgrades = xml_helper.load_xml(GAME_DATA_DIR / 'UpgradeData.xml')
gDocInfo = xml_helper.load_xml(DATA_DIR / 'DocumentInfo')

xml_roots_mapping = {
    'Unit': gUnits,
    'Weapon': gWeapons,
    'Effect': gEffects,
    'UserData': gUserData,
    'Abil': gAbils,
    'Behavior': gBehaviors,
    'Validator': gValidators,
    'Accumulator': gAccumulators,
    'Button': gButtons,
    'Actor': gActors,
    'Upgrade': gUpgrades
}
