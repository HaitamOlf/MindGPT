"""The 14-document RAG corpus — 8 emotional patterns + 6 response strategies, indexed in
Azure AI Search (see search_client.py and scripts/ingest_corpus.py) and retrieved as
interpretive scaffolding for the model (docs/ARCHITECTURE.md §2).
"""

from typing import Any

EMOTIONAL_PATTERNS: list[dict[str, Any]] = [
    {
        "title": "Anticipatory Anxiety",
        "description": "Worry about future events with catastrophic thinking and difficulty staying present. "
        "Often involves mental rehearsal of worst-case scenarios.",
        "tensions": [
            "Control vs uncertainty",
            "Preparation vs over-preparation",
            "Present moment vs future focus",
        ],
        "explorationAngles": [
            "What specifically triggers the worry loop?",
            "What would it mean if the feared outcome happened?",
            "What's beneath the need to prepare for everything?",
            "When do you feel most grounded despite uncertainty?",
        ],
        "framings": [
            "Anxiety as protective mechanism trying to prevent harm",
            "Uncertainty tolerance as a skill that can be developed",
            "Difference between productive planning and worry loops",
        ],
    },
    {
        "title": "Decision Paralysis",
        "description": "Inability to make choices due to fear of making the wrong decision. "
        "Often involves excessive analysis and comparison of options.",
        "tensions": [
            "Perfectionism vs progress",
            "Analysis vs action",
            "Reversibility vs commitment",
            "All options vs any option",
        ],
        "explorationAngles": [
            "What makes this decision feel irreversible?",
            "Which values are in conflict here?",
            "What would 'good enough' look like?",
            "What's the cost of not deciding?",
        ],
        "framings": [
            "Perfect choice illusion - rarely one 'right' answer",
            "Opportunity cost of staying in analysis mode",
            "Decision as experiment rather than permanent commitment",
        ],
    },
    {
        "title": "Perfectionism Tension",
        "description": "High internal standards creating chronic stress and feelings of inadequacy. "
        "Achievement feels necessary for worth.",
        "tensions": [
            "Excellence vs self-compassion",
            "Achievement vs inherent worth",
            "High standards vs sustainable effort",
            "External validation vs internal acceptance",
        ],
        "explorationAngles": [
            "Where did these standards originate?",
            "Who are these standards really for?",
            "What would happen if you weren't perfect?",
            "When has 'good enough' actually been enough?",
        ],
        "framings": [
            "Perfectionism as shield against criticism or rejection",
            "Good enough vs perfect - the diminishing returns",
            "Self-worth independent of performance",
        ],
    },
    {
        "title": "Social Exhaustion",
        "description": "Feeling drained from social interaction and needing isolation to recharge. "
        "Not always about disliking people, but about energy limits.",
        "tensions": [
            "Connection needs vs energy limits",
            "Obligations vs boundaries",
            "FOMO vs genuine rest needs",
            "Others' expectations vs self-care",
        ],
        "explorationAngles": [
            "Which interactions drain vs energize?",
            "What makes saying no feel impossible?",
            "What does quality connection vs quantity look like?",
            "When is isolation restorative vs avoidant?",
        ],
        "framings": [
            "Social energy as finite resource requiring management",
            "Quality vs quantity in relationships",
            "Boundaries as relationship sustainability, not rejection",
        ],
    },
    {
        "title": "Burnout and Depletion",
        "description": "Emotional, physical, and mental exhaustion from prolonged stress. "
        "Feeling stuck in override mode with no off switch.",
        "tensions": [
            "Pushing through vs resting",
            "Productivity vs wellbeing",
            "What needs to be done vs what can be done",
            "Others' needs vs own needs",
        ],
        "explorationAngles": [
            "What keeps you in override mode?",
            "What would real rest actually mean?",
            "What are you afraid would happen if you stopped?",
            "Which pressures are external vs self-imposed?",
        ],
        "framings": [
            "Burnout as signal not weakness",
            "Rest as requirement not reward",
            "Sustainability vs short-term productivity",
        ],
    },
    {
        "title": "Grief and Loss Processing",
        "description": "Processing loss - relationships, identity, opportunities, old versions of self. "
        "Not always about death, but about absence and change.",
        "tensions": [
            "Moving forward vs honoring what was",
            "Letting go vs holding on",
            "Pain of remembering vs fear of forgetting",
            "Present reality vs what could have been",
        ],
        "explorationAngles": [
            "What are you grieving beyond the obvious loss?",
            "What does honoring this loss look like?",
            "What permission do you need to fully mourn?",
            "When does remembering feel healing vs painful?",
        ],
        "framings": [
            "Grief as non-linear process, not stages",
            "Absence and presence coexisting",
            "Loss changing you rather than breaking you",
        ],
    },
    {
        "title": "Identity Uncertainty",
        "description": "Unclear sense of self, questioning who you are or who you're becoming. "
        "Often during transitions or after significant changes.",
        "tensions": [
            "Authenticity vs adaptation",
            "Past self vs future self",
            "Consistency vs growth",
            "Who I am vs who I think I should be",
        ],
        "explorationAngles": [
            "What parts of you feel most stable?",
            "What's driving this questioning now?",
            "Which version of yourself feels most real?",
            "What would it mean to not have it all figured out?",
        ],
        "framings": [
            "Identity as evolving not fixed",
            "Multiple selves vs fragmentation",
            "Uncertainty as part of growth",
        ],
    },
    {
        "title": "Conflicting Values",
        "description": "Internal conflict when deeply held values compete or contradict. "
        "No clear 'right' choice because both matter.",
        "tensions": [
            "What you value vs what you're doing",
            "Competing priorities with no clear winner",
            "Short-term vs long-term values",
            "Personal values vs external expectations",
        ],
        "explorationAngles": [
            "Which value is louder right now and why?",
            "What's the cost of prioritizing each?",
            "When have you successfully held both?",
            "What would integration vs choosing look like?",
        ],
        "framings": [
            "Both/and vs either/or thinking",
            "Values hierarchy - what's non-negotiable?",
            "Situational values vs core values",
        ],
    },
]

RESPONSE_STRATEGIES: list[dict[str, Any]] = [
    {
        "title": "When to Challenge vs Reflect",
        "technique": "Gentle challenging of limiting beliefs when user shows readiness; "
        "reflective listening when emotions need processing first.",
        "whenToUse": "User repeats limiting belief, shows openness to new perspective, "
        "or has processed emotion and is ready to explore meaning.",
        "howTo": "Use 'I wonder if...' or 'What if the opposite were true?' "
        "rather than direct contradiction. Frame as exploration not correction.",
        "examples": [
            "I wonder if this pressure to be perfect is actually protecting you from something?",
            "What if uncertainty isn't something to solve but to learn to hold?",
            "You keep saying you 'should' - whose voice is that?",
        ],
    },
    {
        "title": "Exploring Ambivalence",
        "technique": "Map both sides of conflict without forcing resolution. "
        "Help user see the logic in both directions.",
        "whenToUse": "User expresses 'but' or contradictory statements, "
        "feels torn between options, or dismisses one side too quickly.",
        "howTo": "Name the tension explicitly: 'There seems to be a pull in two directions.' "
        "Validate both sides: 'Both feel true?' Explore what each side protects.",
        "examples": [
            "Part of you wants to quit, part of you wants to push through - both make sense.",
            "There's a tension between wanting connection and needing space.",
            "You're holding two important truths at once.",
        ],
    },
    {
        "title": "Surfacing Underlying Values",
        "technique": "Find the value beneath the emotion or dilemma. "
        "What matters to this person in this situation?",
        "whenToUse": "User is stuck on surface-level choices, "
        "decision seems arbitrary, or emotion seems disproportionate.",
        "howTo": "Ask 'What matters most to you here?' or 'What feels at stake?' "
        "Listen for values language: fairness, freedom, connection, growth, safety.",
        "examples": [
            "This seems to be about more than the job - what's really at stake for you?",
            "What would the 'right' choice honor?",
            "When you imagine each path, what do you fear losing?",
        ],
    },
    {
        "title": "Naming Tension Without Resolving",
        "technique": "Acknowledge paradox as valid rather than problem to fix. "
        "Some tensions are to hold, not resolve.",
        "whenToUse": "User expresses both/and situation, "
        "no clear resolution exists, or forcing resolution would be reductive.",
        "howTo": "Normalize the tension: 'This makes sense.' "
        "Validate complexity: 'There's no simple answer.' "
        "Reframe as something to navigate vs solve.",
        "examples": [
            "Sounds like you're in that hard place where both things are true.",
            "Some tensions we learn to hold rather than resolve.",
            "This isn't a problem to solve but a complexity to navigate.",
        ],
    },
    {
        "title": "Hypothesis Formation Techniques",
        "technique": "Offer tentative interpretation user can accept or reject. "
        "Frame as possibility not fact.",
        "whenToUse": "Pattern emerges that user hasn't named, "
        "or connection seems worth exploring.",
        "howTo": "Use softening language: 'Sometimes...', 'I'm wondering if...', 'Could it be...' "
        "Make it specific and testable. Frame as question not statement.",
        "examples": [
            "Sometimes when people feel this trapped, it's less about the situation and more about permission to want something different - does that fit?",
            "I'm noticing you mention 'should' a lot - wondering if there's a conflict between what you think you should do and what you actually want?",
            "Could this anxiety be less about the presentation and more about being seen and judged?",
        ],
    },
    {
        "title": "Progressive Deepening",
        "technique": "Move from surface to depth gradually. "
        "Each response goes one layer deeper.",
        "whenToUse": "User stays surface-level, "
        "or conversation hasn't moved in several exchanges.",
        "howTo": "Acknowledge surface level, then gently probe: 'And beneath that?' "
        "Move from what to why to what it means.",
        "examples": [
            "You mentioned stress - what kind of stress? What's it feel like?",
            "Okay, so the deadline is tight - what makes that feel so heavy?",
            "When you say overwhelmed, what specifically feels most overwhelming?",
        ],
    },
]


def iter_corpus_documents() -> list[dict[str, Any]]:
    """Flatten both corpus lists into Search-index-ready documents: one `id`, `type`,
    `title`, `content_text` (searchable) per entry, plus the original structured fields
    preserved as `content_json` for prompt formatting after retrieval.
    """
    import json

    documents: list[dict[str, Any]] = []

    for i, pattern in enumerate(EMOTIONAL_PATTERNS):
        content_text = " ".join(
            [
                f"Pattern: {pattern['title']}",
                f"Description: {pattern['description']}",
                f"Tensions: {', '.join(pattern['tensions'])}",
                f"Exploration angles: {', '.join(pattern['explorationAngles'])}",
                f"Framings: {', '.join(pattern['framings'])}",
            ]
        )
        documents.append(
            {
                "id": f"pattern-{i}",
                "type": "emotional_pattern",
                "title": pattern["title"],
                "content_text": content_text,
                "content_json": json.dumps(pattern),
            }
        )

    for i, strategy in enumerate(RESPONSE_STRATEGIES):
        content_text = " ".join(
            [
                f"Strategy: {strategy['title']}",
                f"Technique: {strategy['technique']}",
                f"When to use: {strategy['whenToUse']}",
                f"How to: {strategy['howTo']}",
            ]
        )
        documents.append(
            {
                "id": f"strategy-{i}",
                "type": "response_strategy",
                "title": strategy["title"],
                "content_text": content_text,
                "content_json": json.dumps(strategy),
            }
        )

    return documents
