from __future__ import annotations

from unrealsdk import *
from Mods import ModMenu
from Mods.ModMenu import ClientMethod, ServerMethod

from random import getrandbits

from typing import Dict, Generator, Iterable, List, Optional, Tuple, Union

try:
    from Mods import CommandExtensions
except ImportError:
    CommandExtensions = None


"""
TODO: Consistent Giant health scaling
    Check pawn balance aiclass overrides?

TODO: Adjust loot drop point to prevent floor clipping
    turrets (and Bullymongs?)

TODO: Adjust HUD targeting
    Varkids

TODO: Correct client giant naming regardless of latency.
"""


_ai_roll_blacklist: Tuple[Optional[str], ...] = (
    None,
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
    "CharClass_Tentacle_Slappy": False, # Old Slappy TentacleZ`
    "CharClass_Thresher_Raid": True, # Terramorphus
    "CharClass_TundraPatrol": True, # Will
    "CharClass_Darkness": True, # The Darkness
    "CharClass_Mimic": True, # Mimic
}
""" """

_ai_attributes: Tuple[UObject] = (
    FindObject("AttributeDefinition", "GD_Balance_HealthAndDamage.AIParameters.Attribute_HealthMultiplier"),
    FindObject("AttributeDefinition", "GD_Balance_HealthAndDamage.AIParameters.Attribute_EnemyShieldMaxValueMultiplier"),
    FindObject("AttributeDefinition", "GD_Balance_Experience.Attributes.Attribute_ExperienceMultiplier"),
)
"""A list of AttributeDefinitions that key starting values we modify on Giants' AI classes."""


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

Instead, we can store our data in Unreal Engine objects attached to the WillowAIPawns. For iterating
WillowAIPawns in order to find ones we are interested in, conveniently the game maintains a linked
list of each extant pawn.
"""
class aipawn:
    """A wrapper for WillowAIPawns that provides functionality relevant to our usage of them."""

    __slots__ = "uobject"
    uobject: UObject

    def __init__(self, uobject: UObject):
        self.uobject = uobject


    @classmethod
    def all(cls) -> Generator[aipawn, None, None]:
        """Yield an object for every WillowAIPawn (and subclass) that has an AIClass."""

        # All pawns currently spawned on the map form a linked list with one another, the start of
        # which is accessible from the current world info object.
        pawn = GetEngine().GetCurrentWorldInfo().PawnList
        while pawn is not None:
            # If the pawn has an AIClass, we can be sure it is a WillowAIPawn that is of use to us.
            if pawn.AIClass is not None:
                yield cls(pawn)
            # Continue to the next item in the linked list, if any.
            pawn = pawn.NextPawn


    @property
    def ai_class(self) -> Optional[str]:
        """
        The name of the pawn's AIClassDefinition, if it has one. This can be used to identify what
        type of enemy (or NPC) this pawn represents.
        """
        ai_class = self.uobject.AIClass
        return None if ai_class is None else ai_class.Name


    @property
    def grade_index(self) -> int:
        """
        The grade index of the pawn's balance definition state. This is used to apply modifiers to
        the pawn's balance, however it appears to always be set to -1 (no modifiers) to WillowAIPawn
        objects. The grade index is useful as it is replicated to client instances of the pawn.
        """
        return self.uobject.BalanceDefinitionState.GradeIndex

    @grade_index.setter
    def grade_index(self, grade_index: int) -> None:
        self.uobject.BalanceDefinitionState.GradeIndex = grade_index


    @property
    def balance(self) -> Optional[UObject]:
        """
        The pawn's BalanceDefinition. This contains additional information about the pawn, like
        its name, and whether it is a badass.
        """
        return self.uobject.BalanceDefinitionState.BalanceDefinition


    @property
    def is_badass(self) -> bool:
        """Whether we deem the pawn to be a badass."""

        # If the pawn has a balance, default to its value; otherwise, default to false. Use the
        # default if we don't have a specific override for the pawn's AI class.
        is_champion = False if self.balance is None else self.balance.Champion
        return _ai_badass_overrides.get(self.ai_class, is_champion)


    def encode_ID(self, ID: int) -> None:
        """
        Encode the provided grade index and ID number into a single int. This assumes a grade index
        between -32,767 and 32,768, and an ID between 0 and 65,536.
        """

        # Add 32,767 to the grade index to yield a non-negative integer that is still less than 65,536,
        # thus ensuring it's not using over 16 bits. Shift the ID 16 bits to the right, and OR it in.
        self.grade_index = (self.grade_index + 32767) ^ (ID << 16)


    @property
    def vanilla_grade_index(self) -> int:
        """Return the original grade index that was encoded into the provided grade index value."""

        # Remove any bits from all but the leftmost 16, thus deleting the encoded ID. Subtract the
        # 32,767 that was originally added in, yielding the original grade index.
        return (self.grade_index & 0xFFFF) - 32767


    @property
    def ID(self) -> int:
        """Return the ID number that was encoded into the provided grade index value."""

        # Shift the provided grade index 16 bits to the left, deleting the encoded grade index, and
        # returning the ID as it was originally provided.
        return (self.grade_index >> 16)


    @property
    def is_giant(self):
        """Whether the pawn has been selected for Gigantism."""
        record = self.uobject.DebugPawnMarkerInst
        return record is not None and record.Name == "ReignOfGiants"
    

    def initialize_giant(self) -> None:
        """Configure our custom storage object on a WillowAIPawn that was selected for Gigantism."""

        # The DebugPawnMarkerInst property on WillowAIPawns takes a UObject, and is not utilized
        # anywhere in the vanilla game. Since it's not utilized in vanilla, We may set it to an
        # object of our own creation, and use that to store data relevant to the Giant.
        self.uobject.DebugPawnMarkerInst = ConstructObject("KnowledgeRecord", self.uobject, "ReignOfGiants")
        self.should_drop_loot = True


    def roll_gigantism(self, force: bool = False) -> bool:
        """
        Roll whether the given pawn should be a Giant. If so, apply the server-only modifications to
        it, followed by the server/client modifications, returning the resulting Giant object.
        """

        # If we are currently a client, do not perform a roll.
        if GetEngine().GetCurrentWorldInfo().NetMode == 3:
            return False

        # If the pawn is already selected as a Giant, return it.
        if self.is_giant:
            return True

        # Get the pawn's controller.
        mind = self.uobject.MyWillowMind

        # If the pawn's AI class is in our blacklist, don't roll gigantism for it.
        if mind is None or self.ai_class in _ai_roll_blacklist:
            return False

        # Unless we are in cheat mode or were told to force a giant, We roll 8 bits (1 in 256) to
        # determine whether the pawn will be a giant or not.
        if force or CheatMode.CurrentValue:
            roll = 0
        else:
            roll = getrandbits(8)
            # No pawns that don't roll 0 through 3 will be selected for gigantism.
            if roll > 3:
                return False

        # Pawns that roll a zero are eligible for gigantism no matter who they are. Ones who roll a
        # 0 through 3 are selected if they are a badass enemy.
        if roll != 0 and not self.is_badass:
            return False

        self.initialize_giant()

        # Clone the pawn's AI class, and update the pawn and its controller with the clone.
        self.uobject.AIClass = mind.AIClass = mind.CharacterClass = ConstructObject(
            self.uobject.AIClass.Class, self.uobject, self.uobject.AIClass.Name,
            Template = self.uobject.AIClass
        )

        # Iterate over each of the AI class's starting values so that we may modify them.
        for attribute_starting_value in self.uobject.AIClass.AttributeStartingValues:
            if attribute_starting_value.Attribute in _ai_attributes:
                # Each of the starting vales we modify on the AI class, we quadruple.
                attribute_starting_value.BaseValue.BaseValueScaleConstant *= 4

        # Tell our controller to apply the values from the modified class.
        mind.bCharacterClassInitialized = False
        mind.InitializeCharacterClass()

        return True


    def gigantize(self):
        """Growwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww"""
        if self.uobject.Mesh is None:
            return

        self.uobject.Mesh.Scale3D = (GiantScale.CurrentValue, GiantScale.CurrentValue, GiantScale.CurrentValue)
        self.uobject.MovementSpeedModifier *= 1 + (GiantScale.CurrentValue - 1) * 0.67


    @property
    def vanilla_name_list_index(self) -> int:
        """
        The original name list index for the Giant's pawn before we modified it. We use it when we
        need to temporarily revert the pawn's vanilla name list index to regenerate its name.
        """
        return self.uobject.DebugPawnMarkerInst.FlagIndex if self.is_giant else self.uobject.NameListIndex
    
    @vanilla_name_list_index.setter
    def vanilla_name_list_index(self, index: int) -> None:
        if self.is_giant:
            self.uobject.DebugPawnMarkerInst.FlagIndex = index


    @property
    def should_drop_loot(self) -> bool:
        """
        Whether the Giant should drop loot on death. This is set to `True` on client gigantism, but
        will be toggled off if the Giant has spawned a child pawn.
        """
        return self.is_giant and bool(self.uobject.DebugPawnMarkerInst.Active)
    
    @should_drop_loot.setter
    def should_drop_loot(self, should: bool) -> None:
        if self.is_giant:
            self.uobject.DebugPawnMarkerInst.Active = should


    def giant_name(self) -> str:
        """Generate the Giant-ized name based on the current vanilla name."""

        # If this pawn's balance has not yet been applied, skip it.
        if self.balance is None:
            return None

        # The following is a port of GetTargetName.
        name = None

        if -1 < self.vanilla_name_list_index < _vanilla_name_list_length:
            name = list(_name_list.Names)[self.vanilla_name_list_index]

        # If the pawn is set to display it's parent's name, do so without giant-izing it.
        elif self.uobject.DisplayParentInfo() and self.uobject.GetParent() is not None:
            return self.uobject.GetParent().GetTargetName()

        else:
            if self.uobject.TransformType != 0:
                name = self.uobject.GetTransformedName()
            else:
                name = self.balance.GetDisplayNameAtGrade(-1)

            if name is None and self.uobject.AIClass is not None:
                name = self.uobject.AIClass.DefaultDisplayName

        if name is None:
            return None

        # Before we potentially format this name for a pet presentation, prefix it.
        name = f"{GiantPrefix.CurrentValue} {name}"

        if self.uobject.PlayerMasterPRI is not None:
            masterName = self.uobject.PlayerMasterPRI.GetHumanReadableName()
            if len(masterName) > 0:
                name = self.uobject.MasteredDisplayName.replace("%s", masterName).replace("%n", name)

        return name


    def bequeath_gigantism(self, child: UObject):
        """
        If this pawn is of an AI class which undergoes "transformation" by spawning a child pawn,
        then dying, ensure the child pawn inherits its Gigantism, and that this pawn won't drop loot
        when it "dies."
        """
        if self.is_giant and self.ai_class in _ai_bequeath_whitelist:
            self.should_drop_loot = False
            type(self)(child).roll_gigantism(force=True)


    def drop_loot(self) -> None:
        """
        Drop loot, assuming the pawn is marked to do so, and its AI class is not in our list of ones
        whose pawns should not.
        """
        if self.should_drop_loot and self.ai_class not in _ai_loot_blacklist:
            # Invoke our loot spawning behavior with our UObject as the context.
            LootBehavior.ApplyBehaviorToContext(self.uobject, (), None, None, None, ())


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

_level_address: int = 0
""" """


"""
In co-op play, WillowAIPawns are represented on clients as their own WillowAIPawn instances, that
have various attributes replicated from the host's instance. In Reign Of Giants, we need clients'
instances to be Gigantized when they are Gigantized on the server.

Unfortunately there is no apparent way of easily identifying which WillowAIPawn instances on clients
correspond to ones on host. We solve this by generating an ID number for each pawn, and encoding it
into a property which the game replicates between host and client instances.
"""
_giant_IDs: List[int] = []
"""The IDs for pawns that the server has reported as Giants, in order of their NameListIndex."""


_package: Optional[UPackage]
"""A custom UPackage used to maintain a persistent namespace for our custom UObjects."""

"""
We must ensure we can drop loot for every single variation of enemy in the game, without in any way
altering the enemy's vanilla loot mechanics. To do so, we use a Behavior_SpawnLootAroundPoint to
generate loot from a list of pools at the location where the enemy dies.
"""
LootBehavior: Optional[UObject]
"""The Behavior_SpawnLootAroundPoint object which spawns loot on Giants' death."""


GiantPrefix: ModMenu.Options.Hidden = ModMenu.Options.Hidden(
    Caption="GiantPrefix",
    StartingValue="Giant"
)
"""The SDK Options object that stores the string which is prepended to each Giants' name."""

GiantScale: ModMenu.Options.Hidden = ModMenu.Options.Hidden(
    Caption="GiantScale",
    StartingValue=2.25
)
"""The SDK Options object that stores the float used to scale Giants' meshes."""


CheatMode: ModMenu.Options.Hidden = ModMenu.Options.Hidden(
    Caption="CheatMode",
    StartingValue=False
)
"""The SDK Options object that stores whether to use cheat mode."""


"""
The SDK has difficulties with certain things; namely, strings allocated by the SDK currently cause a
crash when deallocated by Unreal Engine. Also, it rejects tuples being assigned to FStructs if we
attempt to pass None when the field expects a UObject. Both of these issues can be worked around by
using a `set` console command to apply these "problematic" values to properties.
"""
def _set_command(obj: UObject, property: str, value: Union[str, Iterable[str]]) -> None:
    """Perform a console command to set the given object's property to the specified value(s)."""

    if isinstance(value, str):
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


def _defer_to_tick(name: str, callable: Callable[[], Optional[bool]]) -> None:
    """Schedule a routine to be invoked each game tick until it returns True."""

    # Create a wrapper to call the routine that is suitable to be passed to RunHook.
    def tick(caller: UObject, function: UFunction, params: FStruct) -> bool:
        # Invoke the routine. If it returns False, unregister its tick hook.
        if not callable():
            RemoveHook("WillowGame.WillowGameViewportClient.Tick", "ReignOfGiants." + name)

    # Hook the wrapper.
    RunHook("WillowGame.WillowGameViewportClient.Tick", "ReignOfGiants." + name, tick)


def _request_giants() -> Optional[bool]:
    """
    If we currently have both a GRI and a PRI, initialize our names list and request the current
    Giants from the server.
    """

    # If we do not yet have both a GRI and a PRI, we must keep ticking until we do.
    GRI = GetEngine().GetCurrentWorldInfo().GRI
    if GRI is None or GetEngine().GamePlayers[0].Actor.PlayerReplicationInfo is None:
        return True

    # With the GRI, set up our name list, and initialize its names.
    GRI.NameListDef = _name_list
    _set_command(_name_list, "Names", "()")

    # Send the Giants request to the server, and we may stop ticking.
    _mod_instance.ServerRequestGiants()
    

def _prepare_lists() -> Optional[bool]:
    """
    If it has not yet been done in the current map, prepare the name list variables and set of
    WillowAIPawn subclasses.
    """
    global _level_address

    # Get the current world info, and the address of the current level object.
    world_info = GetEngine().GetCurrentWorldInfo()
    current_level_address = world_info.CommittedPersistentLevel.GetAddress()

    # If we are missing either a game replication or player replication object, we are a client in a
    # new game session, and must defer a request for the current Giants state until we have both.
    if world_info.GRI is None or GetEngine().GamePlayers[0].Actor.PlayerReplicationInfo is None:
        _level_address = current_level_address
        _defer_to_tick("RequestGiants", _request_giants)
        return

    # If the address of the current level object matches our existing record, we're still in the
    # same level, and do not need to perform setup.
    if _level_address == current_level_address:
        return
    # With a new level, update our record of its address.
    _level_address = current_level_address

    # If we are currently a client, request the current Giants from the host.
    if GetEngine().GetCurrentWorldInfo().NetMode == 3:
        _defer_to_tick("RequestGiants", _request_giants)
        return

    # Initialize our records of the vanilla name list's length and items.
    global _vanilla_name_list_length, _vanilla_name_list_names
    _vanilla_name_list_length = 0
    _vanilla_name_list_names = ""

    # If the vanilla name list does in fact exist in this map, populate our records with its values.
    if world_info.GRI.NameListDef is not None and world_info.GRI.NameListDef.Names is not None:
        for name in world_info.GRI.NameListDef.Names:
            _vanilla_name_list_length += 1
            _vanilla_name_list_names += _array_string(name)

    # Send the new vanilla name list values to clients.
    _mod_instance.ClientUpdateVanillaNameList(_vanilla_name_list_length, _vanilla_name_list_names)

    # Assign our name list to the GRIs, and schedule an update for the name list's contents.
    world_info.GRI.NameListDef = _name_list
    _defer_to_tick("UpdatePawns", _update_pawns)


def _update_pawns() -> Optional[bool]:
    """
    Update our name list to contain the contents of the vanilla one, as well as the current name of
    each Giant. This should be scheduled to be run on a game tick, so as to consolidate multiple
    requests for updates that may occur in quick succession.
    """

    # Iterate over every current WillowAIPawn object. Record the ID for each pawn that has one, each
    # pawn that does not yet have an ID, and each pawn that is a Giant.
    IDs = set()
    IDless_pawns = []
    giant_pawns = []

    for pawn in aipawn.all():
        ID = pawn.ID
        if ID > 0:
            IDs.add(ID)
        else:
            IDless_pawns.append(pawn)

        if pawn.is_giant:
            giant_pawns.append(pawn)

    # Starting with 1, find IDs that are not currently in use, assigning them to the pawns that did
    # not yet have an ID.
    new_ID = 1
    for IDless_pawn in IDless_pawns:
        while new_ID in IDs:
            new_ID += 1
        IDless_pawn.encode_ID(new_ID)
        new_ID += 1

    # Initialize our list of Giants' IDs, and begin the "array" of new names with the vanilla ones.
    global _giant_IDs
    _giant_IDs = []
    name_list_names = _vanilla_name_list_names

    # For each Giant pawn that was found, add its ID to the list of Giants' IDs, add its name to the
    # names "array," and set its NameListIndex to the index it will be found in the list.
    for giant_index, giant_pawn in enumerate(giant_pawns):
        _giant_IDs.append(giant_pawn.ID)
        name_list_names += _array_string(giant_pawn.giant_name())
        giant_pawn.uobject.NameListIndex = _vanilla_name_list_length + giant_index

    # Apple the new names to the name list, and send the new list of Giants' IDs to clients.
    _set_command(_name_list, "Names", f"({name_list_names})")
    _mod_instance.ClientUpdateGiants(_giant_IDs)


def _gigantize_pawns() -> Optional[bool]:
    """
    From the current list of Giants' IDs, find each Giant pawn, Gigantize them, and update the names
    list with their Gigantized names, in order.
    """

    # Get the current game replication info. If it has not yet been created, tick until it has.
    GRI = GetEngine().GetCurrentWorldInfo().GRI
    if GRI is None:
        return True

    # Create a list of empty strings as long as the number of Giants.
    giant_names = [""] * len(_giant_IDs)

    # For each current pawn, attempt to locate the index of its ID in the list of Giants' IDs.
    for pawn in aipawn.all():
        try:
            giant_index = _giant_IDs.index(pawn.ID)
        # If the pawn's ID is not in the in the list of Giant IDs, skip it.
        except ValueError:
            continue

        # If we encounter a Giant that is not yet had its, balance definition applied, stop here and
        # try again on the next tick.
        if pawn.balance is None:
            return True

        pawn.gigantize()

        # Generate the Giant's name and place it in the names list at the Giant's index.
        giant_names[giant_index] = pawn.giant_name()
        # The Giant's name's index in the names list will be its index relative to the end of
        # the vanilla ones.
        pawn.uobject.NameListIndex = _vanilla_name_list_length + giant_index

    # Start the new names list with the vanilla ones, then append each Giant's name in order.
    name_list_names = _vanilla_name_list_names
    for name in giant_names:
        name_list_names += _array_string(name)

    # Make sure our name list is applied to the world info, and apply our names to it.
    GRI.NameListDef = _name_list
    _set_command(_name_list, "Names", f"({name_list_names})")


# @Hook("WillowGame.WillowAIPawn.PostBeginPlay", "ReignOfGiants")
def _aipawn_post_begin_play(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    Every single WillowAIPawn, even ones without balances, have this method called after being
    spawned.
    """
    _prepare_lists()

    # If we are currently a client, we do not need to do anything here.
    if GetEngine().GetCurrentWorldInfo().NetMode == 3:
        return True

    # Temporarily remove our hook for this method before invoking injecting its call now.
    RemoveHook("WillowGame.WillowAIPawn.PostBeginPlay", "ReignOfGiants")
    DoInjectedCallNext()
    caller.PostBeginPlay()
    RunHook("WillowGame.WillowAIPawn.PostBeginPlay", "ReignOfGiants", _aipawn_post_begin_play)

    # If a bogus name list index was applied to the pawn, sanitize it now to prevent it from kicking
    # in with the names we add to the name list.
    if caller.NameListIndex >= _vanilla_name_list_length:
        caller.NameListIndex = -1
    return False


# @Hook("WillowGame.PopulationFactoryBalancedAIPawn.SetupBalancedPopulationActor", "ReignOfGiants")
def _setup_balanced_population(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    All pawn entities that we are concerned with are passed through a routine that applies a number
    of properties to them, such as their balance definition and spawn point.
    """

    # The new pawn and its "spawn point" object are passed as parameters.
    pawn = params.SpawnedPawn
    spawn = params.SpawnLocationContextObject
    if pawn is None or spawn is None:
        return True

    # If the spawn point has a WillowAIPawn as its Owner, then that is the parent pawn of the new,
    # pawn, so tell it to bequeath its Gigantism to the new pawn, if applicable.
    if spawn.Owner is not None and spawn.Owner.AIClass is not None:
        aipawn(spawn.Owner).bequeath_gigantism(pawn)

    return True


# @Hook("Engine.Pawn.ApplyBalanceDefinitionCustomizations", "ReignOfGiants")
def _apply_balance_customizations(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    All WillowAIPawns that we are interested in will be configured with a balance definition. Once
    it has been assigned to them, this method is called to apply its contents to the pawn's
    properties involving its target name, whether it's a badass, and other things. This must take
    place after any initializations of the pawn for its AI class.
    """
    _prepare_lists()

    if caller.AIClass is None:
        return True

    pawn = aipawn(caller)

    # If we are not a client, Roll Gigantism for the pawn (if it had not already inherited it from
    # its parent in SetupBalancedPopulationActor).
    is_giant = pawn.roll_gigantism()

    # Get the pawn's ID from its grade index. If it has one, revert its grade index to the vanilla
    # value before proceeding. If it doesn't, schedule a pawn update to assign it one.
    ID = pawn.ID
    if ID > 0:
        pawn.grade_index = pawn.vanilla_grade_index
    elif GetEngine().GetCurrentWorldInfo().NetMode != 3:
        _defer_to_tick("UpdatePawns", _update_pawns)

    # Temporarily remove this hook before invoking the original method.
    RemoveHook("Engine.Pawn.ApplyBalanceDefinitionCustomizations", "ReignOfGiants")
    DoInjectedCallNext()
    caller.ApplyBalanceDefinitionCustomizations()
    RunHook("Engine.Pawn.ApplyBalanceDefinitionCustomizations", "ReignOfGiants", _apply_balance_customizations)

    # If the pawn had an ID, re-encode it now.
    if ID > 0:
        pawn.encode_ID(ID)

    # If we are currently a client, we have nothing more to do.
    if GetEngine().GetCurrentWorldInfo().NetMode == 3:
        return False

    # Ensure the resulting name list index applied to the pawn isn't bogus, to prevent it from
    # kicking in with the names we added to the names list.
    if caller.NameListIndex >= _vanilla_name_list_length:
        caller.NameListIndex = -1

    # If we did roll a giant, update its balance-dependent properties, then update the name list.
    if is_giant:
        pawn.vanilla_name_list_index = caller.NameListIndex
        pawn.gigantize()
        _defer_to_tick("UpdatePawns", _update_pawns)

    return False


# @Hook("WillowGame.WillowAIPawn.ReplicatedEvent", "ReignOfGiants")
def _replicated_event(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    WillowAIPawns that exist on the server are only guaranteed to exist on the client when the
    client is engaged with them. When they do, the server periodically sends replicated events about
    them to indicate things like the values of properties having been updated.
    """

    # If we are being notified of this pawn's balance definition state, this instance has just been
    # freshly replicated to this client, so we should check whether it needs to be gigantized.
    if params.VarName == "BalanceDefinitionState" and aipawn(caller).ID in _giant_IDs:
        _defer_to_tick("GigantizePawns", _gigantize_pawns)

    return True


# @Hook("WillowGame.WillowAIPawn.AILevelUp", "ReignOfGiants")
def _ai_level_up(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    When an AI undergoes a transformation that involves it leveling up, this method is called on
    both server and client.
    """

    # If we are a client, we have nothing to do.
    if GetEngine().GetCurrentWorldInfo().NetMode == 3:
        return True

    DoInjectedCallNext()
    caller.AILevelUp()

    # If this pawn is already a Giant, update its name.
    pawn = aipawn(caller)
    if pawn.is_giant:
        _defer_to_tick("UpdatePawns", _update_pawns)

    # If we are not a client player, give the pawn a new roll at being a Giant.
    elif pawn.roll_gigantism():
        pawn.vanilla_name_list_index = caller.NameListIndex
        pawn.gigantize()
        _defer_to_tick("UpdatePawns", _update_pawns)

    return False


# @Hook("WillowGame.Behavior_Transform.ApplyBehaviorToContext", "ReignOfGiants")
def _behavior_transform(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """
    Various WillowAIPawns are able to undergo "transformation" (e.g. Varkids, Goliaths). When this
    occurs, a Behavior_Transform object is invoked with the pawn as the context object, and that
    pawn's TransformType is simply updated with that of the behavior object.
    """

    # If we are a client, we have nothing to do.
    if GetEngine().GetCurrentWorldInfo().NetMode == 3:
        return True

    # When one of our giants has a transform invoked on them, we update their name.
    pawn = aipawn(params.ContextObject)
    if pawn.is_giant:
        params.ContextObject.TransformType = caller.Transform
        _defer_to_tick("UpdatePawns", _update_pawns)

    return True


# @Hook("WillowGame.WillowAIPawn.Died", "ReignOfGiants")
def _died(caller: UObject, function: UFunction, params: FStruct) -> bool:
    """All WillowAIPawns die someday. Circle of WillowAILife."""

    aipawn(caller).drop_loot()
    return True


def _toggle_cheat_mode() -> None:
    """Toggle cheat mode and log a message to console."""
    CheatMode.CurrentValue = not CheatMode.CurrentValue
    ModMenu.SaveModSettings(_mod_instance)
    Log("Reign Of Giants Cheat Mode: " + ("On" if CheatMode.CurrentValue else "Off"))


def _edit_giant_scale(arguments: Sequence[Any]) -> None:
    """Set the scale for Giants and log a message to console."""
    try:
        GiantScale.CurrentValue = float(arguments[0] if isinstance(arguments, list) else arguments.size)
        ModMenu.SaveModSettings(_mod_instance)
        Log(f"Reign Of Giants Giant Size: {GiantScale.CurrentValue}")
    except (IndexError, ValueError):
        Log("Must specify a valid number, e.g.: giantssize 0.5")


def _edit_giant_prefix(arguments: Sequence[Any]) -> None:
    """Set the name prefix for Giants and log a message to console."""
    try:
        GiantPrefix.CurrentValue = arguments[0] if isinstance(arguments, list) else arguments.name
        ModMenu.SaveModSettings(_mod_instance)
        Log(f"Reign Of Giants Giant Name: {GiantPrefix.CurrentValue}")
    except IndexError:
        Log("Must specify a name, e.g.: giantsname Teensie Weensie")


if CommandExtensions is None:
    # @Hook("Engine.PlayerController.ConsoleCommand", "ReignOfGiants.ConsoleCommand")
    def _console_command(caller: UObject, function: UFunction, params: FStruct):
        command, *arguments = params.Command.split(maxsplit=1)

        if command == "giantscheat":
            _toggle_cheat_mode()
            return False
        elif command == "giantssize":
            _edit_giant_scale(arguments)
            return False
        elif command == "giantsname":
            _edit_giant_prefix(arguments)
            return False

        return True


class ReignOfGiants(ModMenu.SDKMod):
    Name: str = "Reign Of Giants"
    Version: str = "1.2"
    Description: str = "Encounter rare, gigantic variants of enemies throughout the Borderlands."
    Author: str = "mopioid"
    Types: ModTypes = ModTypes.Gameplay
    SupportedGames: ModMenu.Game = ModMenu.Game.BL2

    SaveEnabledState: ModMenu.EnabledSaveType = ModMenu.EnabledSaveType.LoadOnMainMenu

    Options: List[ModMenu.Options.Base] = [GiantPrefix, GiantScale, CheatMode]

    @ServerMethod
    def ServerRequestGiants(self, PC: UObject = None) -> None:
        """Request the server send us, a client, the current Giants' ID numbers and name list."""
        self.ClientUpdateVanillaNameList(_vanilla_name_list_length, _vanilla_name_list_names, PC)
        self.ClientUpdateGiants(_giant_IDs, PC)


    @ClientMethod
    def ClientUpdateVanillaNameList(self, length: int, names: str, PC: UObject = None) -> None:
        """Send the current values for the vanilla names list to the client."""
        global _vanilla_name_list_length, _vanilla_name_list_names
        _vanilla_name_list_length = length
        _vanilla_name_list_names = names


    @ClientMethod
    def ClientUpdateGiants(self, IDs: List[int], PC: UObject = None) -> None:
        """Update clients' records of Giants' ID numbers."""
        global _giant_IDs
        _giant_IDs = IDs

        _defer_to_tick("GigantizePawns", _gigantize_pawns)


    def Enable(self) -> None:
        super().Enable()

        """Create our custom package and its subobjects."""
        global _package, _name_list, LootBehavior

        def construct_object(uclass: str, outer: Optional[UObject], name: str) -> UObject:
            path = name if outer is None else f"{UObject.PathName(outer)}.{name}"
            uobject = FindObject(uclass, path)
            if uobject is None:
                uobject = ConstructObject(uclass, outer, name)
                KeepAlive(uobject)
            return uobject

        _package = construct_object("Package", None, "ReignOfGiants")
        _name_list = construct_object("NameListDefinition", _package, "NameList")
        LootBehavior = construct_object("Behavior_SpawnLootAroundPoint", _package, "LootBehavior")

        def _construct_item_pool(name: str, items: Iterable[Tuple[str, Union[str, float]]]) -> UObject:
            """
            Constructs an ItemPoolDefinition with the given object paths and weights. Weights can be
            either a float representing Probability's BaseValueConstant, or a string representing
            the object path to its InitializationDefinition.
            """
            item_pool = ConstructObject("ItemPoolDefinition", LootBehavior, name)

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

        # Create a legendary weapon loot pool that mimics the vanilla legendary pool, except with no
        # pearl drops (these will come from the Tubby pearl pool).
        _legendary_pool = _construct_item_pool("LegendaryWeaponPool", (
            ( "GD_Itempools.WeaponPools.Pool_Weapons_Pistols_06_Legendary",       100.0 ),
            ( "GD_Itempools.WeaponPools.Pool_Weapons_AssaultRifles_06_Legendary",  80.0 ),
            ( "GD_Itempools.WeaponPools.Pool_Weapons_SMG_06_Legendary",            80.0 ),
            ( "GD_Itempools.WeaponPools.Pool_Weapons_Shotguns_06_Legendary",       80.0 ),
            ( "GD_Itempools.WeaponPools.Pool_Weapons_SniperRifles_06_Legendary",   55.0 ),
            ( "GD_Itempools.WeaponPools.Pool_Weapons_Launchers_06_Legendary",      20.0 ),
        ))

        # Create a legendary shield loot pool identical to the vanilla one, except with the omission
        # of the roid shield pool, since it only drops non-unique Bandit shields.
        _shield_pool = _construct_item_pool("LegendaryShieldPool", (
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
        _item_pool = _construct_item_pool("ItemPool", (
            ( "GD_Lobelia_Itempools.WeaponPools.Pool_Lobelia_Pearlescent_Weapons_All", pearl_weight ),
            # The weights of the pools that aren't the Tubby loot pool should add up to 0.2, such
            # that the odds of a Pearl max out at 50% at level 80.
            ( UObject.PathName(_legendary_pool),                              0.080 ),
            ( UObject.PathName(_shield_pool),                                 0.030 ),
            ( "GD_Itempools.GrenadeModPools.Pool_GrenadeMods_06_Legendary",   0.030 ),
            # The Tubby class mod pool should be 3x the weight of the main game class mod pool, such
            # that every legendary class mod has an equal chance of dropping.
            ( "GD_Lobelia_Itempools.ClassModPools.Pool_ClassMod_Lobelia_All", 0.045 ),
            ( "GD_Itempools.ClassModPools.Pool_ClassMod_06_Legendary",        0.015 ),
        ))

        # Retrieve the green items loot pool to serve as the base for our PreLegendaryPool object.
        uncommon_pool = FindObject("ItemPoolDefinition", "GD_Itempools.EnemyDropPools.Pool_GunsAndGear_02_Uncommon")
        _early_pool = ConstructObject("ItemPoolDefinition", LootBehavior, "PreLegendaryPool", Template=uncommon_pool)

        # Set the max level for the PreLegendaryPool to be able to drop items to 5.
        _early_pool.MaxGameStageRequirement = FindObject("AttributeDefinition", "GD_Itempools.Scheduling.Gamestage_05")

        # Set our loot behavior to spawn one instance of the main item pool, or five instances of
        # the pre-legendary loot pool.
        _set_command(LootBehavior, "ItemPools", (UObject.PathName(pool) for pool in (
            _item_pool,
            _early_pool, _early_pool, _early_pool, _early_pool, _early_pool,
        )))

        # Register our hooks.
        RunHook( "WillowGame.WillowAIPawn.PostBeginPlay",                                   "ReignOfGiants", _aipawn_post_begin_play       )
        RunHook( "WillowGame.PopulationFactoryBalancedAIPawn.SetupBalancedPopulationActor", "ReignOfGiants", _setup_balanced_population    )
        RunHook( "Engine.Pawn.ApplyBalanceDefinitionCustomizations",                        "ReignOfGiants", _apply_balance_customizations )
        RunHook( "WillowGame.WillowAIPawn.ReplicatedEvent",                                 "ReignOfGiants", _replicated_event             )
        RunHook( "WillowGame.WillowAIPawn.AILevelUp",                                       "ReignOfGiants", _ai_level_up                  )
        RunHook( "WillowGame.Behavior_Transform.ApplyBehaviorToContext",                    "ReignOfGiants", _behavior_transform           )
        RunHook( "WillowGame.WillowAIPawn.Died",                                            "ReignOfGiants", _died                         )

        if CommandExtensions is None:
            RunHook("Engine.PlayerController.ConsoleCommand", "ReignOfGiants", _console_command)
        else:
            CommandExtensions.RegisterConsoleCommand(
                name = "giantscheat",
                callback = lambda args: _toggle_cheat_mode(),
                splitter = lambda args: [args]
            ).add_argument("void")

            CommandExtensions.RegisterConsoleCommand(
                name = "giantssize",
                callback = lambda args: _edit_giant_scale(args),
                splitter = lambda args: [args]
            ).add_argument("size")

            CommandExtensions.RegisterConsoleCommand(
                name = "giantsname",
                callback = lambda args: _edit_giant_prefix(args),
                splitter = lambda args: [args]
            ).add_argument("name")


    def Disable(self) -> None:
        super().Disable()

        global _package, _name_list, LootBehavior

        def release_object(uclass: str, path: str) -> None:
            uobject = FindObject(uclass, path)
            if uobject is not None:
                uobject.ObjectFlags.A &= ~0x4000

        _name_list = release_object("NameListDefinition", "ReignOfGiants.NameList")
        LootBehavior = release_object("Behavior_SpawnLootAroundPoint", "ReignOfGiants.LootBehavior")
        _package = release_object("Package", "ReignOfGiants")

        # Perform the garbage collection console command to force destruction of the objects.
        GetEngine().GamePlayers[0].Actor.ConsoleCommand("obj garbage", False)

        RemoveHook( "WillowGame.WillowAIPawn.PostBeginPlay",                                   "ReignOfGiants" )
        RemoveHook( "WillowGame.PopulationFactoryBalancedAIPawn.SetupBalancedPopulationActor", "ReignOfGiants" )
        RemoveHook( "Engine.Pawn.ApplyBalanceDefinitionCustomizations",                        "ReignOfGiants" )
        RemoveHook( "WillowGame.WillowAIPawn.ReplicatedEvent",                                 "ReignOfGiants" )
        RemoveHook( "WillowGame.WillowAIPawn.AILevelUp",                                       "ReignOfGiants" )
        RemoveHook( "WillowGame.Behavior_Transform.ApplyBehaviorToContext",                    "ReignOfGiants" )
        RemoveHook( "WillowGame.WillowAIPawn.Died",                                            "ReignOfGiants" )

        if CommandExtensions is None:
            RemoveHook("Engine.PlayerController.ConsoleCommand", "ReignOfGiants")
        else:
            CommandExtensions.UnregisterConsoleCommand("giantscheat")
            CommandExtensions.UnregisterConsoleCommand("giantssize")
            CommandExtensions.UnregisterConsoleCommand("giantsname")

        RemoveHook( "WillowGame.WillowGameViewportClient.Tick", "ReignOfGiants.RequestGiants"  )
        RemoveHook( "WillowGame.WillowGameViewportClient.Tick", "ReignOfGiants.UpdatePawns"    )
        RemoveHook( "WillowGame.WillowGameViewportClient.Tick", "ReignOfGiants.GigantizePawns" )


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
