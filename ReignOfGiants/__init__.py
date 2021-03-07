from __future__ import annotations

from unrealsdk import *
from Mods import ModMenu
from Mods.ModMenu import ClientMethod

from random import getrandbits
from dataclasses import dataclass
from typing import Dict, Generator, Iterable, Optional, Set, Tuple, Union

"""
TODO: Consistent Giant health scaling

TODO: Adjust loot drop point to prevent floor clipping
    turrets

TODO: Adjust HUD targeting
    Varkids
"""

_package: Optional[UPackage]
"""A custom UPackage used to maintain a persistent namespace for our custom UObjects."""


"""
Enemy and NPC spawns in Borderlands 2 are implemented with transient WillowAIPawn objects. The base
concept of Reign Of Giants is to intercept WillowAIPawn objects, perform an RNG roll for their
Gigantism, then perform modifications to ones which roll Gigantism and track them throughout their
life cycle.

One difficulty in working with transient WillowAIPawns is that, once we have taken an interest in
one (i.e. once we have selected it to be a Giant), we have no way with the SDK to guarantee we will
be made aware of its destruction. Any attempt to access a destroyed instance will result in garbage
data or a crash. This means we cannot create lists in Python which track WillowAIPawn objects, and
also we cannot easily associate our own Python data with individual pawns.

Instead, we can store our data in Unreal Engine objects attached to the WillowAIPawns, and then when
we need to find pawns we are interested in, use UObject.FindAll on WillowAIPawn and its subclasses.
"""
_aipawn_uclass: UClass = FindClass("WillowAIPawn")
"""UClass WillowAIPawn"""

_aipawn_subclasses: Set[UClass]
"""The list of all WillowAIPawn subclasses loaded in the current map."""


"""
A significant aspect of Reign Of Giants is the adjusting of individual WillowAIPawns to include
"Giant" in the name displayed to the player. To determine what name is displayed, the game invokes
GetTargetName on its WillowAIPawn. This function accepts an `out` parameter through which it passes
the final name. The SDK cannot alter `out` parameters, so instead we must hijack the mechanisms
accessed in GetTargetName.

GetTargetName checks a series of conditionals to determine the pawn's name, so we must use the first
one to ensure our altered name is chosen. Each WillowAIPawn has a NameListIndex property, an integer
that refers to an entry in the current GameReplicationInfo's NameListDefinition. We can add strings
to this list, and individually set pawn's NameListIndex to point to those new strings.
"""
_name_list: Optional[UObject]
"""A persistent NameListDefinition to which we copy vanilla fixup names, then append our custom
giant names. This will be assigned as the GameReplicationInfo's NameListDef in every map."""

_vanilla_name_list_length: int
"""The original length of the GameReplicationInfo's NameListDefinition for the current map."""

_vanilla_name_list_names: str
"""
The items of the vanilla name list for the current map, in a format suitable for insertion into a
set console command.
"""


"""
We must ensure we can drop loot for every single variation of enemy in the game, without in any way
altering the enemy's vanilla loot mechanics. To do so, we use a Behavior_SpawnLootAroundPoint to
generate loot from a list of pools at the location where the enemy dies.
"""
LootBehavior: Optional[UObject]
"""The Behavior_SpawnLootAroundPoint object which spawns loot on Giants' death."""


_cheat_mode: bool = False
"""Whether or not we are currently in cheat mode."""

"""
The SDK has difficulties with certain things; namely, strings allocated by the SDK currently cause a
crash when deallocated by Unreal Engine. Also, it rejects tuples being assigned to FStructs if we
attempt to pass None when the field expects a UObject. Both of these issues can be worked around by
using a `set` console command to apply these "problematic" values to properties.
"""
def _set_command(obj: UObject, property: str, value: Union[str, Iterable[str]]) -> None:
    """Perform a console command to set the given object's property to the specified value(s)."""

    if type(value) is str:
        command = f"set {UObject.PathName(obj)} {property} {value}"
    else:
        command = f"set {UObject.PathName(obj)} {property} ({','.join(value)})"

    GetEngine().GamePlayers[0].Actor.ConsoleCommand(command, False)


def _array_string(string: str) -> str:
    """
    Return the string with its quotes escaped, enclosed in quotes, followed by a comma. This format
    is suitable for concatenation into an array as the value for a `set` console command.
    """
    string = string.replace('"', '\\"')
    return f"\"{string}\","


def _construct_item_pool(
    outer: UObject,
    name: str,
    items: Iterable[Tuple[str, Union[str, float]]]
) -> UObject:
    """
    Constructs an ItemPoolDefinition with the given object paths and weights. Weights can be either
    a float representing Probability's BaseValueConstant, or a string representing the object path
    to its InitializationDefinition.
    """
    item_pool = ConstructObject("ItemPoolDefinition", outer, name)

    balanced_items = []

    for pool, weight in items:
        if type(weight) is float:
            probability = f"(BaseValueConstant={weight},BaseValueScaleConstant=1)"
        elif type(weight) is str:
            probability = f"(InitializationDefinition={weight},BaseValueScaleConstant=1)"

        balanced_item = f"(ItmPoolDefinition={pool},Probability={probability},bDropOnDeath=True)"
        balanced_items.append(balanced_item)

    _set_command(item_pool, "BalancedItems", balanced_items)

    return item_pool


def _construct_package():
    """Create our custom package and its subobjects."""

    global _package
    _package = FindObject("Package", "ReignOfGiants")
    if _package is None:
        _package = ConstructObject("Package", None, "ReignOfGiants")
        KeepAlive(_package)

    global _name_list
    _name_list = FindObject("Package", "ReignOfGiants.NameList")
    if _name_list is None:
        _name_list = ConstructObject("NameListDefinition", _package, "NameList")
        KeepAlive(_name_list)

    global LootBehavior
    LootBehavior = FindObject("Package", "ReignOfGiants.LootBehavior")
    if LootBehavior is None:
        LootBehavior = ConstructObject("Behavior_SpawnLootAroundPoint", _package, "LootBehavior")
        KeepAlive(LootBehavior)

    # Create a legendary weapon loot pool that mimics the vanilla legendary pool, except with no
    # pearl drops (these will come from the Tubby pearl pool).
    _legendary_pool = _construct_item_pool(LootBehavior, "LegendaryWeaponPool", (
        ( "GD_Itempools.WeaponPools.Pool_Weapons_Pistols_06_Legendary",       100.0 ),
        ( "GD_Itempools.WeaponPools.Pool_Weapons_AssaultRifles_06_Legendary",  80.0 ),
        ( "GD_Itempools.WeaponPools.Pool_Weapons_SMG_06_Legendary",            80.0 ),
        ( "GD_Itempools.WeaponPools.Pool_Weapons_Shotguns_06_Legendary",       80.0 ),
        ( "GD_Itempools.WeaponPools.Pool_Weapons_SniperRifles_06_Legendary",   55.0 ),
        ( "GD_Itempools.WeaponPools.Pool_Weapons_Launchers_06_Legendary",      20.0 ),
    ))

    # Create a legendary shield loot pool identical to the vanilla one, except with the omission of
    # the roid shield pool, since it only drops non-unique Bandit shields.
    _shield_pool = _construct_item_pool(LootBehavior, "LegendaryShieldPool", (
        ( "GD_Itempools.ShieldPools.Pool_Shields_Standard_06_Legendary",         1.0 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_NovaShields_All_06_Legendary",  1.0 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_SpikeShields_All_06_Legendary", 1.0 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_Juggernaut_06_Legendary",       1.0 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_Booster_06_Legendary",          1.0 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_Absorption_06_Legendary",       1.0 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_Impact_06_Legendary",           1.0 ),
        ( "GD_Itempools.ShieldPools.Pool_Shields_Chimera_06_Legendary",          1.0 ),
    ))

    # THe name of the initialization definition object which is used to scale Tubby pearl drop
    # weight based on item level. This maxes out at 0.2 at level 80.
    pearl_weight = "GD_Lobelia_Itempools.Weighting.Weight_Lobelia_Pearlescent_Tubbies"

    # Create the standard item pool from which each Giant's item drop will be selected.
    _item_pool = _construct_item_pool(LootBehavior, "ItemPool", (
        ( "GD_Lobelia_Itempools.WeaponPools.Pool_Lobelia_Pearlescent_Weapons_All", pearl_weight ),
        # The weights of the pools that aren't the Tubby loot pool should add up to 0.2, such that
        # the odds of a Pearl max out at 50% at level 80.
        ( UObject.PathName(_legendary_pool),                              0.080 ),
        ( UObject.PathName(_shield_pool),                                 0.030 ),
        ( "GD_Itempools.GrenadeModPools.Pool_GrenadeMods_06_Legendary",   0.030 ),
        # The Tubby class mod pool should be 3x the weight of the main game class mod pool, such
        # that every legendary class mod has an equal chance of dropping.
        ( "GD_Lobelia_Itempools.ClassModPools.Pool_ClassMod_Lobelia_All", 0.045 ),
        ( "GD_Itempools.ClassModPools.Pool_ClassMod_06_Legendary",        0.015 ),
    ))

    # Retrieve the mixed green items loot pool to serve as the base for our PreLegendaryPool object.
    uncommon_pool = FindObject("ItemPoolDefinition", "GD_Itempools.EnemyDropPools.Pool_GunsAndGear_02_Uncommon")
    _prelegendary_pool = ConstructObject("ItemPoolDefinition", LootBehavior, "PreLegendaryPool", Template=uncommon_pool)

    # Set the max level for the PreLegendaryPool to be able to drop items to 5.
    _prelegendary_pool.MaxGameStageRequirement = FindObject("AttributeDefinition", "GD_Itempools.Scheduling.Gamestage_05")

    # Set our loot behavior to spawn one instance of the main item pool, or five instances of the
    # pre-legendary loot pool.
    _set_command(LootBehavior, "ItemPools", (UObject.PathName(pool) for pool in (
        _item_pool,
        _prelegendary_pool, _prelegendary_pool, _prelegendary_pool, _prelegendary_pool, _prelegendary_pool,
    )))


def _destroy_package():
    """Unmark our custom package and objects for preservation, and garbage collect them."""

    global _name_list
    _name_list = FindObject("Package", "ReignOfGiants.NameList")
    if _name_list is not None:
        _name_list.ObjectFlags.A &= ~0x4000
        _name_list = None

    global LootBehavior
    LootBehavior = FindObject("Package", "ReignOfGiants.LootBehavior")
    if LootBehavior is not None:
        LootBehavior.ObjectFlags.A &= ~0x4000
        LootBehavior = None

    global _package
    _package = FindObject("Package", "ReignOfGiants")
    if _package is not None:
        _package.ObjectFlags.A &= ~0x4000
        _package = None

    # Perform the garbage collection console command to force destruction of the objects.
    GetEngine().GamePlayers[0].Actor.ConsoleCommand("obj garbage", False)


def _prepare_lists() -> None:
    """
    If it has not yet been done in the current map, prepare the name list variables and set of
    WillowAIPawn subclasses.
    """

    # Retrieve the current world info object. If it does not yet have a GameReplicationInfo object,
    # force its initialization now.
    world_info = GetEngine().GetCurrentWorldInfo()
    if world_info.GRI is None:
        world_info.Game.PreBeginPlay()

    # If the GRI's name list is already set to our persistent one, we do not need to perform setup.
    elif world_info.GRI.NameListDef is _name_list:
        return

    # Initialize our records of WillowAIPawn subclasses, and the name list's length and items.
    global _aipawn_subclasses, _vanilla_name_list_length, _vanilla_name_list_names
    _aipawn_subclasses = {_aipawn_uclass}
    _vanilla_name_list_length = 0
    _vanilla_name_list_names = ""

    # Iterate over every currently loaded UClass. If the UClass's super class (or any of its super
    # classes, etc.) are WillowAIPawn, add it to our list of WillowAIPawn subclasses.
    for uclass in FindAll("Class"):
        superclass = uclass.SuperField
        while superclass is not None:
            if superclass is _aipawn_uclass:
                _aipawn_subclasses.add(uclass)
                break
            superclass = superclass.SuperField

    # If the vanilla name list does in fact exist, 
    if world_info.GRI.NameListDef is not None and world_info.GRI.NameListDef.Names is not None:
        for name in GRI.NameListDef.Names:
            _vanilla_name_list_length += 1
            _vanilla_name_list_names += _array_string(name)

    # Assign our name list to the GRI, and schedule an update for its contents.
    world_info.GRI.NameListDef = _name_list
    _schedule_name_list_update()


def _schedule_name_list_update() -> None:
    if GetEngine().GetCurrentWorldInfo().NetMode != 3:
        RunHook("WillowGame.WillowGameViewportClient.Tick", "ReignOfGiants", _update_name_list)


def _update_name_list(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    Update our name list to contain the contents of the vanilla one, as well as the current name of
    each Giant. This should be scheduled to be run on a game tick, so as to consolidate multiple
    requests for updates that may occur in quick succession.
    """

    # Copy our vanilla name list details to serve as the basis for the new ones.
    name_index = _vanilla_name_list_length
    names = _vanilla_name_list_names

    # For each Giant, regenerate their name, append it to the name list array string, and set their
    # name list index to reference the current slot in the name list.
    for giant in _giant.all():
        name = giant.generate_name()
        if name is not None:
            names += _array_string(name)
            giant.pawn.NameListIndex = name_index
            name_index += 1

    # Perform the console command to update our name list with the new Names array.
    _set_command(_name_list, "Names", f"({names})")
    _mod_instance.ClientUpdateGiants(names)

    RemoveHook("WillowGame.WillowGameViewportClient.Tick", "ReignOfGiants")
    return True


_ai_roll_blacklist: Tuple[str, ...] = (
    "CharClass_Bloodwing", # Bloodwing
    "CharClass_BunkerBoss", # Bunker
    "CharacterClass_Orchid_BossWorm", # Leviathan
    "CharClass_DragonHeart_Raid", # Fake healthbar for Ancient Dragons
    "CharClass_GoliathBossProxy", # Fake healthbar for Happy Couple
)
"""AIClassDefinition names whose pawns should not roll as Giants."""

_ai_bequeath_whitelist: Tuple[str, ...] = (
    "CharClass_InfectedPodTendril", # Infected Pods
    "CharClass_Pumpkinhead", # Pumpkin Kingpin
    "CharClass_Skeleton_Fire", # Flaming Skeleton
    "CharClass_Skeleton_King", # Skeleton King
    # Varkids
    "CharClass_Anemone_BugMorph_Basic",
    "CharClass_BugMoprhUltimate",
    "CharClass_BugMorph",
    "CharClass_BugMorph_Adult",
    "CharClass_Bugmorph_Badass",
    "CharClass_Bugmorph_SuperBadass",
    "CharClass_Nast_BugMorph_BadassBloodhound",
    "CharClass_Nast_BugMorphTreasure",
    "CharClass_Nasturtium_BugMorph_Acid",
    "CharClass_Nasturtium_BugMorph_Badass",
    "CharClass_Nasturtium_BugMorph_Bloodhound",
    "CharClass_Nasturtium_BugMorph_Fire_Holiday",
    "CharClass_Nasturtium_BugMorph_Miami",
    "CharClass_Nasturtium_BugMorph_Rasta",
    "CharClass_Nasturtium_BugMorph_Shock",
    "CharClass_Nasturtium_BugMorph_Tropical",
)
"""AIClassDefinition names whose pawns should pass on Gigantism to their child pawns."""

_ai_loot_blacklist: Tuple[str, ...] = (
    "CharClass_Assassin_Hologram", # Zer0's hologram
    "CharClass_Aster_Roland_Turret", # Roland's turret
    "CharClass_DeathTrap", # Deathtrap
    "CharClass_RakkVolcanic", # Volcanic Rakk
    "CharClass_RolandDeployableTurret", # Roland's turret
    "CharClass_Scorpio", # Axton's Turret
    "CharClass_Skeleton_King", # Skeleton Kings (these drop loot via their head pawns)
    "CharClass_TargetDummy", # Target dummy
    "CharClass_TargetDummy_Shield", # Target dummy
    "CharClass_TargetDummy_Target", # Target dummy
    "CharClass_TargetDummyBot", # Target dummy
)
"""AIClassDefinition names whose pawns should not drop loot on death."""

_ai_badass_overrides: Dict[str, bool] = {
    "CharacterClass_Anemone_SandWormBoss_1": True, # Haderax
    "CharacterClass_Anemone_SandWormQueen": True, # Sandworm Queen
    "CharacterClass_Orchid_SandWormQueen": True, # Sand Worms Queens
    "CharClass_Anemone_Cassius": True, # Cassius
    "CharClass_Anemone_Hector": True, # Hector
    "CharClass_Anemone_Infected_Golem_Badass": True, # Infected Badass Golem
    "CharClass_Anemone_Lt_Angvar": True, # Angvar
    "CharClass_Anemone_Lt_Bolson": True, # Bolson
    "CharClass_Anemone_Lt_Hoffman": True, # Hoffman
    "CharClass_Anemone_Lt_Tetra": True, # Tetra
    "CharClass_Anemone_UranusBOT": True, # Uranus
    "CharClass_Aster_GenericNPC": False, # Flamerock Citizen
    "CharClass_BlingLoader": True, # BLING Loader
    "CharClass_Boll": True, # Boll
    "CharClass_BugMorph_Bee_Badass": True, # Badass Stabber Jabber
    "CharClass_CommunityMember": False, # Flamerock Citizen?
    "CharClass_Dragon": True, # Ancient Dragons
    "CharClass_FlyntSon": True, # Sparky Flynt
    "CharClass_GateGuard": False, # Davlin
    "CharClass_Golem_SwordInStone": True, # Unmotivated Golem
    "CharClass_Iris_BikeRiderMarauderBadass": True, # Badass Biker
    "CharClass_Iris_MotorMamaBike": True, # Motor Mama's Bike
    "CharClass_Iris_Raid_PyroPete": True, # Raid Pete
    "CharClass_Juggernaut": True, # Juggernauts
    "CharClass_Orchid_Deserter_Cook": True, # Terry
    "CharClass_Orchid_Deserter_Deckhand": True, # Deckhand
    "CharClass_Orchid_LittleSis": True, # Lil' Sis
    "CharClass_Orchid_RaidShaman": True, # Master Gee
    "CharClass_RakkBadass": True, # Badass Rakks
    "CharClass_Sage_AcquiredTaste_Creature": True, # Bulstoss
    "CharClass_Sage_Ep3_Creature": True, # Thermitage
    "CharClass_Sage_Raid_Beast": True, # Vorac
    "CharClass_Sage_Raid_BeastMaster": True, # Chief Ngwatu
    "CharClass_Sage_Rhino": True, # Der monwahtever
    "CharClass_Sage_RhinoBasass": True, # Borok Badasses
    "CharClass_Sage_ScaylionQueen": True, # Queen Scaylions
    "CharClass_SarcasticSlab": True, # Sarcastic Slab
    "CharClass_Skeleton_Immortal": False, # Immortal Skeleton
    "CharClass_Spiderpants": True, # Spiderpants
    "CharClass_SpiderTank_Baricade": False, # BAR-TNK
    "CharClass_Tentacle_Slappy": False, # Old Slappy Tentacle
    "CharClass_Thresher_Raid": True, # Terramorphus
    "CharClass_TundraPatrol": True, # Will
}

_ai_attributes: Tuple[UObject] = (
    FindObject("AttributeDefinition", "GD_Balance_HealthAndDamage.AIParameters.Attribute_HealthMultiplier"),
    FindObject("AttributeDefinition", "GD_Balance_HealthAndDamage.AIParameters.Attribute_EnemyShieldMaxValueMultiplier"),
    FindObject("AttributeDefinition", "GD_Balance_Experience.Attributes.Attribute_ExperienceMultiplier"),
)
"""A list of AttributeDefinitions that key starting values we modify on Giants' AI classes."""


@dataclass
class _giant:
    """
    A lean wrapper for WillowAIPawns that have been selected for Gigantism, that provides
    functionality relevant to their Giant status.
    """

    __slots__ = ("pawn")
    pawn: UObject


    @classmethod
    def new(cls, pawn: UObject) -> _giant:
        """Configure our custom storage object on a WillowAIPawn that was selected for Gigantism."""
        giant = cls(pawn)

        # The DebugPawnMarkerInst property on WillowAIPawns takes a UObject, and is not utilized
        # anywhere in the vanilla game. Since it's not utilized in vanilla, We may set it to an
        # object of our own creation, and use that to store data relevant to the Giant.
        pawn.DebugPawnMarkerInst = ConstructObject("KnowledgeRecord", pawn, "ReignOfGiants")

        giant.balance_applied = False
        giant.should_drop_loot = True

        return giant


    @classmethod
    def get(cls, pawn: UObject) -> Optional[_giant]:
        """If the given pawn was selected as a Giant, return a Giant object for it."""

        # If the pawn does not have a DebugPawnMarkerInst with our own object, it is not a Giant.
        if pawn.DebugPawnMarkerInst is None or pawn.DebugPawnMarkerInst.Name != "ReignOfGiants":
            return None

        return cls(pawn)


    @classmethod
    def all(cls) -> Generator[_giant, None, None]:
        """Yields a Giant object for every extant pawn that was selected for gigantism."""

        # Iterate over every loaded WillowAIPawn subclass, and from those, every member object.
        for aipawn_subclass in _aipawn_subclasses:
            for pawn in UObject.FindAll(aipawn_subclass.Name):
                # If the pawn is Giant, yield its Giant object.
                giant = cls.get(pawn)
                if giant is not None:
                    yield giant


    @classmethod
    def roll(cls, pawn: UObject, force: bool = False) -> Optional[_giant]:
        """
        Roll whether the given pawn should be a Giant. If so, apply the server-only modifications to
        it, followed by the server/client modifications, returning the resulting Giant object.
        """

        # If the pawn is already selected as a Giant, return it.
        giant = cls.get(pawn)
        if giant is not None:
            return giant

        # If the pawn's AI class is in our blacklist, don't roll gigantism for it.
        if pawn.AIClass is None or pawn.MyWillowMind is None or pawn.AIClass.Name in _ai_roll_blacklist:
            return None

        # Unless we are in cheat mode or were told to force a giant, We roll 8 bits (1 in 256) to
        # determine whether the pawn will be a giant or not.
        if force or _cheat_mode:
            roll = 0
        else:
            roll = getrandbits(1)
            # No pawns that don't roll 0 through 3 will be selected for gigantism.
            if roll > 3:
                return None
            # Determine whether the pawn is a badass by referencing our badass override dictionary,
            # falling back to its balance if we don't have an override for it.
            is_badass = _ai_badass_overrides.get(pawn.AIClass.Name)
            if is_badass is None:
                balance = pawn.BalanceDefinitionState.BalanceDefinition
                is_badass = False if balance is None else balance.Champion

        # Pawns that roll a zero are eligible for gigantism no matter who they are. Ones who roll a
        # 0 through 3 are selected if they are a badass enemy.
        if roll == 0 or is_badass:
            # Create the Giant's object, perform the server-side modifications to it, apply its
            # balance state, then perform the client-side modifications to it.
            giant = cls.new(pawn)
            giant.server_giantize()

        return giant


    def server_giantize(self) -> None:
        """Perform modifications to the pawn relevant to the server."""

        # Get the pawn's controller.
        mind = self.pawn.MyWillowMind

        # Clone the pawn's AI class, and update the pawn and its controller with the clone.
        self.pawn.AIClass = mind.AIClass = mind.CharacterClass = ConstructObject(
            self.pawn.AIClass.Class, self.pawn, self.pawn.AIClass.Name,
            Template = self.pawn.AIClass
        )

        # Iterate over each of the AI class's starting values so that we may modify them.
        for attribute_starting_value in self.pawn.AIClass.AttributeStartingValues:
            if attribute_starting_value.Attribute in _ai_attributes:
                # Each of the starting vales we modify on the AI class, we quadruple.
                attribute_starting_value.BaseValue.BaseValueScaleConstant *= 4

        # Tell our controller to apply the values from the modified class.
        mind.bCharacterClassInitialized = False
        mind.InitializeCharacterClass()


    def client_gigantize(self):
        """Perform modifications to the pawn relevant to both the server and clients."""

        # Growwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww
        self.pawn.Mesh.Scale3D = (2.25, 2.25, 2.25)
        _schedule_name_list_update()


    @property
    def balance_applied(self) -> bool:
        """Whether the Giant has had its BalanceDefinitionState set up by the game."""
        return bool(self.pawn.DebugPawnMarkerInst.Marked)
    
    @balance_applied.setter
    def balance_applied(self, applied: bool) -> None:
        self.pawn.DebugPawnMarkerInst.Marked = applied


    @property
    def vanilla_name_list_index(self) -> int:
        """
        The original name list index for the Giant's pawn before we modified it. We use it when we
        need to temporarily revert the pawn's vanilla name list index to regenerate its name.
        """
        return self.pawn.DebugPawnMarkerInst.FlagIndex
    
    @vanilla_name_list_index.setter
    def vanilla_name_list_index(self, index: int) -> None:
        self.pawn.DebugPawnMarkerInst.FlagIndex = index


    @property
    def should_drop_loot(self) -> bool:
        """
        Whether the Giant should drop loot on death. This is set to `True` on client gigantism, but
        will be toggled off if the Giant has spawned a child pawn.
        """
        return bool(self.pawn.DebugPawnMarkerInst.Active)
    
    @should_drop_loot.setter
    def should_drop_loot(self, should: bool) -> None:
        self.pawn.DebugPawnMarkerInst.Active = should


    def generate_name(self) -> str:
        """Generate the Giant-ized name based on the current vanilla name."""

        if not self.balance_applied:
            return None

        # Record the custom name list index that we have assigned to the pawn, then revert it to the
        # vanilla one.
        self.pawn.NameListIndex = self.vanilla_name_list_index

        # The following is a port of GetTargetName.
        name = None

        if -1 < self.pawn.NameListIndex < _vanilla_name_list_length:
            name = names[self.pawn.NameListIndex]

        # If the pawn is set to display it's parent's name, do so without giant-izing it.
        elif self.pawn.DisplayParentInfo() and self.pawn.GetParent() is not None:
            return self.pawn.GetParent().GetTargetName()

        else:
            if self.pawn.TransformType != 0:
                name = self.pawn.GetTransformedName()

            elif self.pawn.BalanceDefinitionState.BalanceDefinition != None:
                name = self.pawn.BalanceDefinitionState.BalanceDefinition.GetDisplayNameAtGrade(-1)

            if name is None and self.pawn.AIClass is not None:
                name = self.pawn.AIClass.DefaultDisplayName

        if name is None:
            return None

        # Before we potentially format this name for a pet presentation, prefix it with "Giant".
        name = "Giant " + name

        if self.pawn.PlayerMasterPRI is not None:
            masterName = self.pawn.PlayerMasterPRI.GetHumanReadableName()
            if len(masterName) > 0:
                name = self.pawn.MasteredDisplayName.replace("%s", masterName).replace("%n", name)

        return name


    def drop_loot(self) -> None:
        """Drop loot, if applicable."""

        if self.should_drop_loot and self.pawn.AIClass.Name not in _ai_loot_blacklist:
            LootBehavior.ApplyBehaviorToContext(self.pawn, (), None, None, None, ())


# @Hook("WillowGame.WillowAIPawn.PostBeginPlay", "ReignOfGiants")
def _post_begin_play(caller: UObject, function: UFunction, params: FStruct) -> bool:
    if GetEngine().GetCurrentWorldInfo().NetMode == 3:
        return True

    RemoveHook("WillowGame.WillowAIPawn.PostBeginPlay", "ReignOfGiants")
    DoInjectedCallNext()
    caller.PostBeginPlay()
    RunHook("WillowGame.WillowAIPawn.PostBeginPlay", "ReignOfGiants", _post_begin_play)

    _prepare_lists()

    if caller.NameListIndex >= _vanilla_name_list_length:
        caller.NameListIndex = -1
    return False


# @Hook("WillowGame.PopulationFactoryBalancedAIPawn.SetupBalancedPopulationActor", "ReignOfGiants")
def _setup_balanced_population(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    All pawn entities that we are concerned with are passed through a routine that applies a number
    of properties to them, such as their balance definition and spawn point.
    """
    pawn = params.SpawnedPawn
    if pawn is None:
        return True

    # The pawn's "spawn point" object is passed as a parameter to the method. If this object is non-
    # null and also itself has an Owner property, that may contain a parent pawn for this pawn.
    spawn_location = params.SpawnLocationContextObject
    if spawn_location is None or spawn_location.Owner is None:
        return True

    # Check whether the potential parent pawn is a Giant WillowAIPawn. If so, and if its AI class is
    # in our list of pawns who should bequeath their Gigantism, we will do so to the new pawn.
    parent_giant = _giant.get(spawn_location.Owner)
    if parent_giant is None or parent_giant.pawn.AIClass.Name not in _ai_bequeath_whitelist:
        return True

    parent_giant.should_drop_loot = False
    _giant.roll(pawn, force=True)
    return True


# @Hook("Engine.Pawn.ApplyBalanceDefinitionCustomizations", "ReignOfGiants")
def _apply_balance_customizations(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    All WillowAIPawns that we are interested in will be configured with a balance definition. Once
    it has been assigned to them, this method is called to apply its contents to the pawn's
    properties involving its target name, whether it's a badass, and other things. This must take
    place after any initializations of the pawn for its AI class.
    """

    # If we are on client, we do not need to perform any work here.
    if GetEngine().GetCurrentWorldInfo().NetMode == 3:
        return True

    if caller.Class not in _aipawn_subclasses:
        return True

    # Roll Gigantism for the pawn (if it had not already inherited it from its parent in
    # SetupBalancedPopulationActor).
    giant = _giant.roll(caller)

    # Temporarily remove this hook before invoking the original method.
    RemoveHook("Engine.Pawn.ApplyBalanceDefinitionCustomizations", "ReignOfGiants")
    DoInjectedCallNext()
    caller.ApplyBalanceDefinitionCustomizations()
    RunHook("Engine.Pawn.ApplyBalanceDefinitionCustomizations", "ReignOfGiants", _apply_balance_customizations)

    # Ensure the resulting name list index applied to the pawn isn't bogus, to prevent it from
    # kicking in with the names we added to the names list.
    if caller.NameListIndex >= _vanilla_name_list_length:
        caller.NameListIndex = -1

    # If we did roll a giant, update its balance-dependent properties, then update the name list.
    if giant is not None:
        giant.vanilla_name_list_index = caller.NameListIndex
        giant.balance_applied = True
        giant.client_gigantize()

    return False


_replicated_giant_vars: Tuple[str, ...] = (
    "BalanceDefinitionState",
    "ReplicatedBehaviorConsumerState",
    "ReplicatedBehaviorEvent",
    "ReplicatedInstanceDataState"
)


# @Hook("WillowGame.WillowAIPawn.ReplicatedEvent", "ReignOfGiants")
def _replicated_event(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    WillowAIPawns that exist on the server are only guaranteed to exist on the client when the
    client is engaged with them. When they do, the server periodically sends replicated events about
    them to indicate things like the values of properties having been updated.
    """

    # If we are being notified of this pawn's balance definition state, this instance has just been
    # freshly spawned on this client, so we should check whether it needs to be gigantized.
    if params.VarName in _replicated_giant_vars:
        _prepare_lists()

        if caller.NameListIndex >= _vanilla_name_list_length:
            _giant.new(caller).client_gigantize()

    return True


# @Hook("WillowGame.WillowAIPawn.AILevelUp", "ReignOfGiants")
def _ai_level_up(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    When an AI undergoes a transformation that involves it leveling up, this method is called on
    both server and client.
    """
    DoInjectedCallNext()
    caller.AILevelUp()

    # If this pawn is already a Giant, update its name.
    giant = _giant.get(caller)
    if giant is not None:
        _schedule_name_list_update()

    # If we are not a client player, give the pawn a new roll at being a Giant.
    elif GetEngine().GetCurrentWorldInfo().NetMode != 3:
        giant = _giant.roll(caller)
        if giant is not None:
            giant.vanilla_name_list_index = caller.NameListIndex
            giant.balance_applied = True
            giant.client_gigantize()

    elif caller.NameListIndex >= _vanilla_name_list_length:
        _giant.new(caller).client_gigantize()

    return False


# @Hook("WillowGame.Behavior_Transform.ApplyBehaviorToContext", "ReignOfGiants")
def _behavior_transform(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    Various WillowAIPawns are able to undergo "transformation" (e.g. Varkids, Goliaths). When this
    occurs, a Behavior_Transform object is invoked with the pawn as the context object, and that
    pawn's TransformType is simply updated with that of the behavior object.
    """
    giant = _giant.get(params.ContextObject)
    if giant is None:
        return True

    # When one of our giants has a transform invoked on them, we update their name.
    giant.pawn.TransformType = caller.Transform
    _schedule_name_list_update()
    return False


# @Hook("WillowGame.WillowAIPawn.Died", "ReignOfGiants")
def _died(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """All WillowAIPawns die someday. Circle of WillowAILife."""

    # If the pawn was a giant, invoke our loot behavior with it.
    giant = _giant.get(caller)
    if giant is not None:
        giant.drop_loot()

    return True


# @Hook("Engine.PlayerController.ConsoleCommand", "ReignOfGiants")
def _console_command(caller: UObject, function: UFunction, params: FStruct):
    if params.Command != "giantscheat":
        return True

    global _cheat_mode
    _cheat_mode = not _cheat_mode
    Log("Reign Of Giants Cheat Mode: " + ("On" if _cheat_mode else "Off"))
    return False


class ReignOfGiants(ModMenu.SDKMod):
    Name: str = "Reign Of Giants"
    Version: str = "1.1"
    Description: str = "Encounter rare, gigantic variants of enemies throughout the Borderlands."
    Author: str = "mopioid"
    Types: ModTypes = ModTypes.Gameplay
    SupportedGames: ModMenu.Game = ModMenu.Game.BL2

    SaveEnabledState: ModMenu.EnabledSaveType = ModMenu.EnabledSaveType.LoadOnMainMenu


    @ClientMethod
    def ClientUpdateGiants(self, names: str) -> None:
        _prepare_lists()
        _set_command(_name_list, "Names", f"({names})")


    def Enable(self) -> None:
        super().Enable()

        _construct_package()

        RunHook( "WillowGame.WillowAIPawn.PostBeginPlay",                                   "ReignOfGiants", _post_begin_play              )
        RunHook( "WillowGame.PopulationFactoryBalancedAIPawn.SetupBalancedPopulationActor", "ReignOfGiants", _setup_balanced_population    )
        RunHook( "Engine.Pawn.ApplyBalanceDefinitionCustomizations",                        "ReignOfGiants", _apply_balance_customizations )
        RunHook( "WillowGame.WillowAIPawn.ReplicatedEvent",                                 "ReignOfGiants", _replicated_event             )
        RunHook( "WillowGame.WillowAIPawn.AILevelUp",                                       "ReignOfGiants", _ai_level_up                  )
        RunHook( "WillowGame.Behavior_Transform.ApplyBehaviorToContext",                    "ReignOfGiants", _behavior_transform           )
        RunHook( "WillowGame.WillowAIPawn.Died",                                            "ReignOfGiants", _died                         )
        RunHook( "Engine.PlayerController.ConsoleCommand",                                  "ReignOfGiants", _console_command              )


    def Disable(self) -> None:
        super().Disable()

        _destroy_package()

        RemoveHook( "WillowGame.WillowAIPawn.PostBeginPlay",                                   "ReignOfGiants" )
        RemoveHook( "WillowGame.PopulationFactoryBalancedAIPawn.SetupBalancedPopulationActor", "ReignOfGiants" )
        RemoveHook( "Engine.Pawn.ApplyBalanceDefinitionCustomizations",                        "ReignOfGiants" )
        RemoveHook( "WillowGame.WillowAIPawn.ReplicatedEvent",                                 "ReignOfGiants" )
        RemoveHook( "WillowGame.WillowAIPawn.AILevelUp",                                       "ReignOfGiants" )
        RemoveHook( "WillowGame.Behavior_Transform.ApplyBehaviorToContext",                    "ReignOfGiants" )
        RemoveHook( "WillowGame.WillowAIPawn.Died",                                            "ReignOfGiants" )
        RemoveHook( "Engine.PlayerController.ConsoleCommand",                                  "ReignOfGiants" )


_mod_instance = ReignOfGiants()

if __name__ == "__main__":
    for mod in Mods:
        if mod.Name == _mod_instance.Name:
            if mod.IsEnabled:
                mod.Disable()
            Mods.remove(mod)
            _mod_instance.__class__.__module__ = mod.__class__.__module__
            break

ModMenu.RegisterMod(_mod_instance)
