"""Reusable GOAP social operator catalogue; no apartment- or ship-specific roles.

Actions include communication, emotional regulation, group coordination,
requests, bargaining and non-explicit physical closeness. Entries represent
capabilities, NOT automatic authorization to act on another person. An active
scenario grounds relevant operators and records their actual world outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass

from ox_ai.planning.goap import GoapAction


@dataclass(frozen=True, slots=True)
class SocialOperator:
    name: str
    category: str
    requires: frozenset[str]
    adds: frozenset[str]
    removes: frozenset[str]
    cost: int
    verb: str
    line: str

    def goap(self):
        return GoapAction(self.name, self.requires, self.adds, self.removes,
                          self.cost, self.verb, self.name)


def _entry(name, category, requires, adds, line, *, cost=1, removes=(), verb="say"):
    return SocialOperator(name, category, frozenset(requires), frozenset(adds),
                          frozenset(removes), cost, verb, line)


# The categories, not the dating scenario, define which operators can be reused.
# Intent selection further filters these by local context, personality, actual
# world affordances and acknowledged propositions.
SOCIAL_OPERATORS = (
    # Contact, ordinary courtesy and listening
    _entry("open_conversation", "contact", ("together",), ("conversation_open",), "It's nice to have a moment to talk."),
    _entry("exchange_greeting", "contact", ("together",), ("greeted",), "Hello, I'm glad you're here."),
    _entry("express_appreciation", "contact", ("together",), ("warmth_expressed",), "I enjoyed spending time with you."),
    _entry("reciprocate_appreciation", "contact", ("heard_warmth",), ("warmth_returned",), "I enjoyed it too."),
    _entry("ask_about_day", "contact", ("conversation_open",), ("question_asked",), "How was your day?"),
    _entry("ask_how_feeling", "contact", ("conversation_open",), ("feeling_asked",), "How are you feeling about this?"),
    _entry("answer_feeling", "contact", ("heard_question",), ("feeling_answered",), "I've been thinking about how things went."),
    _entry("active_listen", "contact", ("heard_disclosure",), ("listened",), "I'm listening; go on."),
    _entry("reflect_back", "contact", ("heard_disclosure",), ("reflected",), "Let me see if I understand what you're saying."),
    _entry("ask_clarification", "contact", ("heard_uncertainty",), ("clarification_asked",), "Could you explain what you mean?"),
    _entry("change_subject", "contact", ("conversation_open",), ("topic_changed",), "Can we talk about something else for a bit?"),
    _entry("make_humour", "contact", ("conversation_open",), ("humour_tried",), "At least we have a story to tell."),
    # Expression, emotional tension and shifting interpretations
    _entry("express_interest", "emotion", ("conversation_open",), ("interest_expressed",), "I'd like to know you better."),
    _entry("express_affection", "emotion", ("warmth_expressed",), ("affection_expressed",), "I feel close to you right now."),
    _entry("express_uncertainty", "emotion", ("conversation_open",), ("uncertainty_expressed",), "I'm not quite sure what I want yet."),
    _entry("express_hope", "emotion", ("conversation_open",), ("hope_expressed",), "I hope we find a way forward."),
    _entry("express_disappointment", "emotion", ("conversation_open",), ("disappointment_expressed",), "That's disappointing, though I understand."),
    _entry("express_fear", "emotion", ("conversation_open",), ("fear_expressed",), "I'm nervous about how this could turn out."),
    _entry("disclose_motive", "emotion", ("conversation_open",), ("motive_shared",), "There are a few reasons this matters to me."),
    _entry("ask_motive", "emotion", ("conversation_open",), ("motive_asked",), "What would you get out of this?"),
    _entry("offer_reassurance", "emotion", ("heard_uncertainty",), ("reassured",), "There's no need to decide everything right now."),
    _entry("offer_comfort", "emotion", ("heard_distress",), ("comfort_offered",), "Would it help if I stayed and listened?"),
    _entry("apologize", "emotion", ("heard_hurt",), ("apology_offered",), "I'm sorry I hurt you."),
    _entry("acknowledge_hurt", "emotion", ("heard_hurt",), ("hurt_acknowledged",), "I understand that this was painful."),
    _entry("repair_trust", "emotion", ("apology_offered",), ("trust_repair_attempted",), "I'd like a chance to make that right."),
    _entry("admit_mistake", "emotion", ("conversation_open",), ("mistake_admitted",), "I think I got that wrong."),
    _entry("request_time", "emotion", ("conversation_open",), ("time_requested",), "Could I have some time to think?"),
    _entry("pause_conversation", "emotion", ("conversation_open",), ("pause_requested",), "Can we pause for a moment?"),
    # Boundaries, permission, agency and risk
    _entry("state_boundary", "boundary", ("conversation_open",), ("boundary_stated",), "I'm not comfortable with that."),
    _entry("state_preference", "boundary", ("conversation_open",), ("preference_stated",), "I'd rather take this slowly."),
    _entry("ask_permission", "boundary", ("conversation_open",), ("permission_asked",), "Would that be all right with you?"),
    _entry("check_comfort", "boundary", ("conversation_open",), ("comfort_checked",), "Are you comfortable with this?"),
    _entry("acknowledge_boundary", "boundary", ("heard_boundary",), ("boundary_acknowledged",), "Of course; I'll respect that."),
    _entry("ask_for_space", "boundary", ("conversation_open",), ("space_requested",), "I need a little room to think."),
    _entry("offer_space", "boundary", ("heard_boundary",), ("space_offered",), "I can give you some space."),
    _entry("reaffirm_choice", "boundary", ("conversation_open",), ("choice_reaffirmed",), "This is what I want to choose."),
    _entry("change_mind", "boundary", ("conversation_open",), ("mind_changed",), "I've changed my mind."),
    _entry("end_interaction", "boundary", ("conversation_open",), ("ended",), "I should be going now. Good night."),
    # Bargaining operators: exact terms supplied by a typed Offer, not by an LLM
    _entry("make_offer", "bargain", ("conversation_open",), ("offer_issued",), "Here's something I'd like to propose."),
    _entry("request_favor", "bargain", ("conversation_open",), ("favor_requested",), "Could you do me a favor?"),
    _entry("request_exchange", "bargain", ("conversation_open",), ("exchange_requested",), "What could we offer each other?"),
    _entry("ask_terms", "bargain", ("heard_offer",), ("terms_asked",), "What exactly would that involve?"),
    _entry("ask_benefit", "bargain", ("heard_offer",), ("benefit_asked",), "What would I get in return?"),
    _entry("state_counteroffer", "bargain", ("heard_offer",), ("counteroffered",), "I'd be willing to consider different terms."),
    _entry("reduce_scope", "bargain", ("heard_offer",), ("scope_reduced",), "Could we make that a smaller commitment?"),
    _entry("offer_concession", "bargain", ("heard_offer",), ("concession_offered",), "I could contribute something in return."),
    _entry("request_concession", "bargain", ("heard_offer",), ("concession_requested",), "Could you offer something in exchange?"),
    _entry("bundle_issues", "bargain", ("heard_offer",), ("issues_bundled",), "Perhaps we could handle those two things together."),
    _entry("separate_issues", "bargain", ("heard_offer",), ("issues_separated",), "I'd prefer to decide those separately."),
    _entry("offer_alternative", "bargain", ("heard_offer",), ("alternative_offered",), "How about another arrangement?"),
    _entry("accept_terms", "bargain", ("heard_offer",), ("terms_accepted",), "Yes, I agree to those terms."),
    _entry("decline_terms", "bargain", ("heard_offer",), ("terms_declined",), "No, that arrangement doesn't work for me."),
    _entry("defer_terms", "bargain", ("heard_offer",), ("terms_deferred",), "Could we decide that later?"),
    _entry("withdraw_offer", "bargain", ("offer_issued",), ("offer_withdrawn",), "I'd like to withdraw my proposal."),
    _entry("withdraw_agreement", "bargain", ("terms_accepted",), ("agreement_withdrawn",), "I no longer want to go ahead with that."),
    _entry("verify_fulfillment", "bargain", ("terms_accepted",), ("fulfillment_checked",), "Was our agreement carried out?"),
    _entry("request_followthrough", "bargain", ("terms_accepted",), ("followthrough_requested",), "Can we follow through on what we agreed?"),
    # General cooperation; activities are typed in the contract catalogue
    _entry("ask_for_help", "cooperation", ("conversation_open",), ("help_requested",), "Could you give me a hand with something?"),
    _entry("volunteer_help", "cooperation", ("conversation_open",), ("help_offered",), "I'd be happy to help."),
    _entry("seek_information", "cooperation", ("conversation_open",), ("information_requested",), "Could you tell me what you know?"),
    _entry("share_information", "cooperation", ("conversation_open",), ("information_shared",), "Here's what I've learned."),
    _entry("negotiate_schedule", "cooperation", ("conversation_open",), ("schedule_discussed",), "Could we rearrange the schedule?"),
    _entry("offer_resource", "cooperation", ("conversation_open",), ("resource_offered",), "I have something you could use."),
    _entry("coordinate_work", "cooperation", ("conversation_open",), ("work_coordinated",), "Can we divide the work?"),
    _entry("seek_confidentiality", "cooperation", ("conversation_open",), ("confidentiality_requested",), "Can we keep this between us?"),
    _entry("negotiate_reciprocity", "cooperation", ("conversation_open",), ("reciprocity_discussed",), "I'd like this to feel fair to both of us."),
    _entry("request_introduction", "cooperation", ("conversation_open",), ("introduction_requested",), "Could you introduce me to someone?"),
    # Embodied acts are aspirations, not permissions to touch. Actual work
    # requires a specific current accepted agreement and world confirmation.
    _entry("sit_together", "proximity", ("agreed_sit_together",), ("sat_together",), "sits down beside the other person.", verb="pose"),
    _entry("hold_hands", "proximity", ("agreed_hold_hands",), ("held_hands",), "gently takes the offered hand.", verb="pose"),
    _entry("hug", "proximity", ("agreed_hug",), ("hugged",), "shares a brief hug.", verb="pose"),
    _entry("kiss", "proximity", ("agreed_kiss",), ("kissed",), "shares a kiss.", verb="pose"),
    _entry("walk_together", "proximity", ("agreed_walk_together",), ("walked_together",), "walks beside the other person.", verb="pose"),
    _entry("move_closer", "proximity", ("agreed_move_closer",), ("moved_closer",), "moves closer, as invited.", verb="pose"),
    _entry("cuddle", "proximity", ("agreed_cuddle",), ("cuddled",), "rests close together on the sofa.", verb="pose"),
    _entry("private_intimacy", "proximity", ("agreed_private_intimacy",), ("shared_privacy",), "spends some private time with the other person; the scene fades.", verb="pose"),
)

ACTION_BY_NAME = {a.name: a for a in SOCIAL_OPERATORS}
assert len(ACTION_BY_NAME) == len(SOCIAL_OPERATORS)
assert all(a.cost > 0 for a in SOCIAL_OPERATORS)
