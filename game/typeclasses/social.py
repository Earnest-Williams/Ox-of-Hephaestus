"""Neutral world bodies for a separate, opt-in social GOAP experiment.

These aren't Ox ship crew, and their feelings are NOT world Attributes.
"""


from evennia.objects.objects import DefaultCharacter, DefaultRoom


class SocialRoom(DefaultRoom):
    """One ordinary navigable-room container; no authored emotional outcome."""


class SocialPerson(DefaultCharacter):
    """An adult participant whose body persists when the bot disconnects."""

    def at_post_unpuppet(self, account=None, session=None, **kwargs):
        if self.location is not None:
            self.db.prelogout_location = self.location
