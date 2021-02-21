from unrealsdk import *
from Mods import ModMenu
from Mods.ModMenu import Hook

from random import getrandbits
from typing import Optional, Set

"""
TODO: Client pawn transformations
TODO: Adjust HUD targeting
    Varkids
TODO: Giant Four Kings should spawn giant head, but themselves not drop loot on death
TODO: TPS support
    giant pawn naming
    loot pool
    possible exclusions
        RK5
        sentinel
"""

_package: Optional[UPackage]
"""A custom UPackage used to maintain a persistent namespace for our custom UObjects."""


"""
To determine what name to display to the player for a given enemy, the game invokes GetTargetName
on its WillowAIPawn. This function accepts an `out` parameter through which it passes the final
name. The SDK cannot alter `out` parameters, so instead we must hijack the mechanisms accessed in
GetTargetName.

GetTargetName checks a series of conditionals to determine the pawn's name, so we must use the first
one to ensure our altered name is chosen. Each WillowAIPawn has a NameListIndex property, an integer
that refers to an entry in the current GameReplicationInfo's NameListDefinition. We can add strings
to this list, and individually set pawn's NameListIndex to point to those new strings.
"""
_vanilla_names_list_length: int
"""Records the original length of the GameReplicationInfo's NameListDefinition for the current map."""

_name_list_def: Optional[UObject]
"""A persistent NameListDefinition to which we copy vanilla fixup names, then append our custom
giant names. This will be assigned as the GameReplicationInfo's NameListDef in every map."""


ItemPool: Optional[UObject]
"""The ItemPoolDefinition object from which giants item drops are selected."""

_giants: Set[UObject]
"""A set used to record WillowAIPawns that have been selected for gigantism."""


def _prepare_lists() -> None:
    """Prepare the name list definition and set of giant pawns if necessary for the current map."""

    # Pull up the current GameReplicationInfo's NameListDefinition. If it already matches our
    # persistent one, we do not need to perform initialization.
    GRI = GetEngine().GetCurrentWorldInfo().GRI
    if GRI.NameListDef is _name_list_def:
        return

    # Get the contents of the vanilla name list (or create an empty list if there is none).
    global _vanilla_names_list_length
    if GRI.NameListDef is None or GRI.NameListDef.Names is None:
        _name_list_def.Names = []
        _vanilla_names_list_length = 0
    else:
        names = list(GRI.NameListDef.Names)
        _name_list_def.Names = names
        _vanilla_names_list_length = len(names)

    GRI.NameListDef = _name_list_def

    # Initialize our set for tracking giants' pawns.
    global _giants
    _giants = set()


def _generate_name(pawn: UObject) -> str:
    """A port of GetTargetName to insert "Giant" into what the vanilla name would have been."""
    name = None

    if -1 < pawn.NameListIndex < _vanilla_names_list_length:
        name = names[pawn.NameListIndex]
    elif pawn.DisplayParentInfo() and pawn.GetParent() is not None:
        name = pawn.GetTargetName()
    else:
        if pawn.TransformType != 0:
            name = pawn.GetTransformedName()
        elif pawn.BalanceDefinitionState.BalanceDefinition != None:
            name = pawn.BalanceDefinitionState.BalanceDefinition.GetDisplayNameAtGrade(-1)
        if name is None and pawn.AIClass is not None:
            name = pawn.AIClass.DefaultDisplayName

    name = "Giant " + name

    if pawn.PlayerMasterPRI is not None:
        masterName = pawn.PlayerMasterPRI.GetHumanReadableName()
        if len(masterName) > 0:
            name = pawn.MasteredDisplayName.replace("%s", masterName).replace("%n", name)

    return name


def _giantize(pawn: UObject) -> None:
    """Perform the visual alterations on a pawn that was designated for gigantism."""

    # Growwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww
    pawn.Mesh.Scale3D = (2.25, 2.25, 2.25)

    names = list(_name_list_def.Names)
    pawn.NameListIndex = len(names)
    names.append(_generate_name(pawn))
    _name_list_def.Names = names


_blacklisted_ai = [
    "CharClass_BunkerBoss", # Bunker
    "CharacterClass_Orchid_BossWorm", # Leviathan
    "CharClass_DragonHeart_Raid", # Fake healthbar for Ancient Dragons
    "CharClass_GoliathBossProxy", # Fake healthbar for Happy Couple
]


# AttributeDefinition objects we use to locate starting value structures in AIClassDefinitions.
_health_attribute: UObject = FindObject("AttributeDefinition", "GD_Balance_HealthAndDamage.AIParameters.Attribute_HealthMultiplier")
_shield_attribute: UObject = FindObject("AttributeDefinition", "GD_Balance_HealthAndDamage.AIParameters.Attribute_EnemyShieldMaxValueMultiplier")
_xp_attribute: UObject = FindObject("AttributeDefinition", "GD_Balance_Experience.Attributes.Attribute_ExperienceMultiplier")


# @Hook("Engine.Pawn.InitializeBalanceDefinitionState", "ReignOfGiants.InitializedBalance")
def _initialized_balance(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    All WillowAIPawns that we are interested in will have their balance definition state initialized
    at some point. This assigns various attributes involved in determining their name, and whether
    the pawn is a badass, and other things. It must take place after any initializations of the pawn
    for its AI class.

    We use this time to roll whether or not a pawn should be a giant, then perform the various
    giant-related alterations on it.
    """

    # If this pawn is not a WillowAIPawn, or if its AI class is blacklisted, or if it was already
    # selected for gigantism, ignore it.
    if caller.Class.Name != "WillowAIPawn" or caller.AIClass.Name in _blacklisted_ai:
        return True

    _prepare_lists()

    # Roll whether or not this pawn will be a giant. Use 6 bits of randomness (1 in 64) if the pawn
    # is a badasses, otherwise 8 bits (1 in 256).
    roll = getrandbits(6 if params.BalanceDefinition.Champion else 8)
    # roll = getrandbits(1) # 50% chance
    # roll = 0 # 100% chance
    if roll == 0:
        _giants.add(caller)

        # Clone the pawn's AI class, and iterate over its starting values to alter its health,
        # shield, and XP reward multipliers.
        caller.AIClass = ConstructObject(caller.AIClass.Class, Template=caller.AIClass, Outer=caller)
        for attribute_starting_value in caller.AIClass.AttributeStartingValues:

            if attribute_starting_value.Attribute is _health_attribute:
                attribute_starting_value.BaseValue.BaseValueConstant *= 4

            elif attribute_starting_value.Attribute is _shield_attribute:
                attribute_starting_value.BaseValue.BaseValueConstant *= 4

            elif attribute_starting_value.Attribute is _xp_attribute:
                attribute_starting_value.BaseValue.BaseValueScaleConstant *= 4

        # Assign the new class to the pawn's controller, and apply its values to the pawn.
        mind = caller.MyWillowMind
        mind.AIClass = mind.CharacterClass = caller.AIClass
        mind.bCharacterClassInitialized = False
        mind.InitializeCharacterClass()

        # With the new class initialized, we may finally proceed with the balance definition.
        DoInjectedCallNext()
        caller.InitializeBalanceDefinitionState(params.BalanceDefinition, params.GradeIndex)

        # With the balance definition initialized, perform our visual gigantism!
        _giantize(caller)

        # One of the pawn's values that gets synced to client games is its balance's grade
        # index. Having already applied our BalanceDefinitionState, we may now alter it, such
        # that clients see the alterations. We take advantage of this by using a GradeIndex >=
        # 69,000,000 to indicate to clients that this pawn is a giant. Add 69,420,000 to the
        # vanilla index, to account for a vanilla value as low as -420,000.
        caller.BalanceDefinitionState.GradeIndex += 69420000
        return False

    DoInjectedCallNext()
    caller.InitializeBalanceDefinitionState(params.BalanceDefinition, params.GradeIndex)

    # If this pawn is not a giant, ensure it doesn't have any bogus NameListIndex that would kick in
    # with the names we added to the names list.
    if caller.NameListIndex >= _vanilla_names_list_length:
        caller.NameListIndex = -1

    return False


# @Hook("WillowGame.WillowAIPawn.ReplicatedEvent", "ReignOfGiants.ReplicatedEvent")
def _replicated_event(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    WillowAIPawns that exist on the server are only guaranteed to exist on the client when the
    client is engaged with them. When they do, the server periodically sends replicated events about
    them to indicate things like the values of properties having been updated.

    We use these replicated events as client to become aware of pawns and their giant status.
    """

    # We are only interested in the balance definition state having been updated. This event should
    # only occur once per replication of a client side pawn.
    if params.VarName != "BalanceDefinitionState":
        return True

    _prepare_lists()

    # If the server has set the balance definition state's grade index to > 69,000,000, it is a
    # giant. Subtract the 69,420,000 to return it to its vanilla value, then perform giantization.
    if caller.BalanceDefinitionState.GradeIndex >= 69000000:
       caller.BalanceDefinitionState.GradeIndex -= 69420000
       _giantize(caller)

    # If this pawn is not a giant, ensure it doesn't have any bogus NameListIndex that would kick in
    # with the names we added to the names list.
    elif caller.NameListIndex >= _vanilla_names_list_length:
        caller.NameListIndex = -1

    return True


# @Hook("WillowGame.Behavior_Transform.ApplyBehaviorToContext", "ReignOfGiants.BehaviorTransform")
def _behavior_transform(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    Various WillowAIPawns (e.g. Varkids, Goliaths) are able to undergo "transformation." When this
    occurs, a Behavior_Transform object is invoked with the pawn as the context object, and that
    pawn's TransformType is simply updated with that of the behavior object.

    When one of our giants has a transform invoked on them, we update their name.
    """
    pawn = params.ContextObject
    if pawn not in _giants:
        return True

    pawn.TransformType = caller.Transform

    names = list(_name_list_def.Names)
    names[pawn.NameListIndex] = _generate_name(pawn)
    _name_list_def.Names = names

    return False


# @Hook("WillowGame.WillowAIPawn.Died", "ReignOfGiants.Died")
def _died(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    All WillowAIPawns die someday. Circle of life.

    When one of our giant pawns dies, we perform cleanup, and also determine whether they need to
    pass on their giant status to any other pawn, or drop loot.
    """
    if caller not in _giants:
        return True

    _giants.remove(caller)

    # Best we can do to remove the custom name from the NameListDefinition is to replace its array
    # entry with an empty string. (Other methods that actually remove the entry, and adjust each
    # remaining giant pawn's NameListIndex, resulted in crashes.) This causes in a very negligible
    # memory leak for the remainder of the stay in the map. C'est la vie.
    names = list(_name_list_def.Names)
    names[caller.NameListIndex] = ""
    _name_list_def.Names = names

    # Pawns which have both a TransformType, and one child pawn, are simulating a transformation
    # into a new pawn. This new pawn should inherit gigantism (if it has not already rolled
    # gigantism itself), and its parent should not drop loot during the transformation. From the
    # pawn's controller, get a list of its child controllers, and from each of those, their pawns.
    child_pawns = [child_mind.MyWillowPawn for child_mind in caller.MyWillowMind.SpawnChildren]
    if caller.TransformType != 0 and len(child_pawns) == 1:
        child_pawn = child_pawns[0]
        if child_pawn not in _giants:
            _giantize(child_pawn)
            _giants.add(child_pawn)
            child_pawn.BalanceDefinitionState.GradeIndex += 69420000

    # If the pawn is not transformed or has no child pawns, it is truly dead, and should drop loot.
    else:
        # To be able to use the game's functionality of spawning items from pools, we construct a
        # Behavior_SpawnLootAroundPoint object and invoke it. Seemingly all other methods require
        # things the SDK doesn't currently support such as `out` params or new FStructs.
        lootBehavior = ConstructObject("Behavior_SpawnLootAroundPoint", caller)
        lootBehavior.SpawnVelocityRelativeTo = 3 # SPAWNAROUNDPOINTBASIS_ContextActor
        lootBehavior.ItemPools = [ItemPool]
        lootBehavior.ApplyBehaviorToContext(caller, (), None, None, None, ())

    return True


class ReignOfGiants(ModMenu.SDKMod):
  Name: str = "Reign Of Giants"
  Version: str = "1.0"
  Description: str = "Encounter rare, gigantic variants of enemies throughout the Borderlands."
  Author: str = "mopioid"
  Types: ModTypes = ModTypes.Gameplay
  SupportedGames: ModMenu.Game = ModMenu.Game.BL2

  SaveEnabledState: ModMenu.EnabledSaveType = ModMenu.EnabledSaveType.LoadOnMainMenu

  def __init__(self):
      ModMenu.LoadModSettings(self)

  def Enable(self):

    global _package
    _package = FindObject("Package", "ReignOfGiants")
    if _package is None:
        _package = ConstructObject("Package", Name="ReignOfGiants", Outer=None)
        KeepAlive(_package)

    global _name_list_def
    _name_list_def = FindObject("NameListDefinition", "ReignOfGiants.NameList")
    if _name_list_def is None:
        _name_list_def = ConstructObject("NameListDefinition", _package, "NameList")
        KeepAlive(_name_list_def)

    global ItemPool
    ItemPool = FindObject("ItemPoolDefinition", "ReignOfGiants.ItemPool")
    if ItemPool is None:
        ItemPool = ConstructObject("ItemPoolDefinition", _package, "ItemPool")
        KeepAlive(ItemPool)

    balanced_items = []

    for pool, weight in [
        ( "GD_Itempools.WeaponPools.Pool_Weapons_All_06_Legendary",                4 ),
        ( "GD_Lobelia_Itempools.WeaponPools.Pool_Lobelia_Pearlescent_Weapons_All", 4 ),
        ( "GD_Lobelia_Itempools.ClassModPools.Pool_ClassMod_Lobelia_All",          3 ),
        ( "GD_Itempools.ClassModPools.Pool_ClassMod_06_Legendary",                 1 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_All_06_Legendary",                2 ),
        ( "GD_Itempools.GrenadeModPools.Pool_GrenadeMods_06_Legendary",            2 ),
    ]:
        # As the SDK cannot assign arrays of FStructs with null objects, we must use a console command
        # to set our pools as the ItemPoolDefinition's BalancedItems.
        probability = f"(BaseValueConstant={weight},BaseValueScaleConstant=1)"
        balanced_item = f"(ItmPoolDefinition={pool},Probability={probability},bDropOnDeath=True)"
        balanced_items.append(balanced_item)

    balanced_items = f"set ReignOfGiants.ItemPool BalancedItems ({','.join(balanced_items)})"
    GetEngine().GamePlayers[0].Actor.ConsoleCommand(balanced_items, False)

    RunHook("Engine.Pawn.InitializeBalanceDefinitionState", "ReignOfGiants", _initialized_balance)
    RunHook("WillowGame.WillowAIPawn.ReplicatedEvent", "ReignOfGiants", _replicated_event)
    RunHook("WillowGame.Behavior_Transform.ApplyBehaviorToContext", "ReignOfGiants", _behavior_transform)
    RunHook("WillowGame.WillowAIPawn.Died", "ReignOfGiants", _died)

  def Disable(self):
    RemoveHook("Engine.Pawn.InitializeBalanceDefinitionState", "ReignOfGiants")
    RemoveHook("WillowGame.WillowAIPawn.ReplicatedEvent", "ReignOfGiants")
    RemoveHook("WillowGame.Behavior_Transform.ApplyBehaviorToContext", "ReignOfGiants")
    RemoveHook("WillowGame.WillowAIPawn.Died", "ReignOfGiants")

    global _package
    _package.ObjectFlags.A &= ~0x4000
    _package = None

    global _name_list_def
    _name_list_def.ObjectFlags.A &= ~0x4000
    _name_list_def = None

    global ItemPool
    ItemPool.ObjectFlags.A &= ~0x4000
    ItemPool = None

    GetEngine().GamePlayers[0].Actor.ConsoleCommand("obj garbage", False)


ModMenu.RegisterMod(ReignOfGiants())
