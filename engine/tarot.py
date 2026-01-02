import random

def deterministic_shuffle(seq, seed):
    rng = random.Random(seed)
    out = list(seq)      # don’t mutate original
    rng.shuffle(out)
    return out

major_arcana = [
    '0 - The Fool',
    'I - The Magician',
    'II - The High Priestess',
    'III - The Empress',
    'IV - The Emperor',
    'V - The Hierophant',
    'VI - The Lovers',
    'VII - The Chariot',
    'VIII - Strength',
    'IX - The Hermit',
    'X - Wheel of Fortune',
    'XI - Justice',
    'XII - The Hanged Man',
    'XIII - Death',
    'XIV - Temperance',
    'XV - The Devil',
    'XVI - The Tower',
    'XVII - The Star',
    'XVIII - The Moon',
    'XIX - The Sun',
    'XX - Judgement',
    'XXI - The World'
]

minor_arcana = [
 'Ace','Two','Three','Four', 'Five',
 'Six', 'Seven','Eight', 'Nine','Ten', 
 'Page','Knight', 'Queen','King'
]

_typed_arcana = {
    'wands/fire': [n + ' of Wands' for n in minor_arcana], # Creativity, passion, action.
    'cups/water': [n + ' of Cups' for n in minor_arcana], # Emotions, relationships, intuition.
    'pentacles/earth': [n + ' of Pentacles' for n in minor_arcana], # Intellect, challenges, truth.
    'swords/air': [n + ' of Swords' for n in minor_arcana] # Material world, work, finances.
}

_all_cards = [
    *major_arcana,
    *_typed_arcana['wands/fire'],
    *_typed_arcana['cups/water'],
    *_typed_arcana['pentacles/earth'],
    *_typed_arcana['swords/air']
]

card_meanings = {
    # --- Major Arcana ---
    '0 - The Fool': 'Beginnings, innocence, leap of faith, untapped potential.',
    'I - The Magician': 'Willpower, manifestation, skill, focused intent.',
    'II - The High Priestess': 'Intuition, mystery, hidden knowledge, inner voice.',
    'III - The Empress': 'Creation, nurture, abundance, growth.',
    'IV - The Emperor': 'Authority, structure, stability, leadership.',
    'V - The Hierophant': 'Tradition, teaching, spiritual authority, conformity.',
    'VI - The Lovers': 'Union, choice, values alignment, relationships.',
    'VII - The Chariot': 'Determination, control, victory through effort.',
    'VIII - Strength': 'Inner courage, compassion, quiet resilience.',
    'IX - The Hermit': 'Introspection, solitude, inner guidance.',
    'X - Wheel of Fortune': 'Cycles, fate, change, turning points.',
    'XI - Justice': 'Fairness, truth, accountability, balance.',
    'XII - The Hanged Man': 'Surrender, new perspective, suspension.',
    'XIII - Death': 'Transformation, endings, rebirth, release.',
    'XIV - Temperance': 'Balance, moderation, integration, harmony.',
    'XV - The Devil': 'Attachment, temptation, illusion, material bondage.',
    'XVI - The Tower': 'Sudden upheaval, revelation, collapse of false structures.',
    'XVII - The Star': 'Hope, renewal, healing, faith.',
    'XVIII - The Moon': 'Illusion, fear, dreams, subconscious influence.',
    'XIX - The Sun': 'Joy, clarity, success, vitality.',
    'XX - Judgement': 'Awakening, reckoning, calling, renewal.',
    'XXI - The World': 'Completion, wholeness, fulfillment, integration.',

    # --- Wands / Fire ---
    'Ace of Wands': 'Spark of inspiration, new passion, creative force.',
    'Two of Wands': 'Planning, future vision, personal power.',
    'Three of Wands': 'Expansion, foresight, momentum.',
    'Four of Wands': 'Stability, celebration, foundation.',
    'Five of Wands': 'Conflict, competition, creative friction.',
    'Six of Wands': 'Recognition, victory, public success.',
    'Seven of Wands': 'Defense, perseverance, standing ground.',
    'Eight of Wands': 'Speed, movement, rapid progress.',
    'Nine of Wands': 'Resilience, persistence, last stand.',
    'Ten of Wands': 'Burden, responsibility, burnout.',
    'Page of Wands': 'Curiosity, exploration, youthful energy.',
    'Knight of Wands': 'Bold action, adventure, impulsiveness.',
    'Queen of Wands': 'Confidence, charisma, creative leadership.',
    'King of Wands': 'Vision, authority, inspired command.',

    # --- Cups / Water ---
    'Ace of Cups': 'Emotional beginning, love, compassion.',
    'Two of Cups': 'Mutual connection, partnership, harmony.',
    'Three of Cups': 'Celebration, friendship, shared joy.',
    'Four of Cups': 'Apathy, contemplation, emotional withdrawal.',
    'Five of Cups': 'Loss, grief, disappointment.',
    'Six of Cups': 'Nostalgia, memory, innocence.',
    'Seven of Cups': 'Illusion, choices, wishful thinking.',
    'Eight of Cups': 'Emotional departure, seeking deeper meaning.',
    'Nine of Cups': 'Contentment, satisfaction, emotional fulfillment.',
    'Ten of Cups': 'Harmony, family, lasting happiness.',
    'Page of Cups': 'Emotional openness, creativity, sensitivity.',
    'Knight of Cups': 'Romance, idealism, emotional pursuit.',
    'Queen of Cups': 'Empathy, intuition, emotional wisdom.',
    'King of Cups': 'Emotional balance, calm authority.',

    # --- Pentacles / Earth ---
    'Ace of Pentacles': 'Opportunity, prosperity, new material start.',
    'Two of Pentacles': 'Balance, adaptability, juggling priorities.',
    'Three of Pentacles': 'Collaboration, craftsmanship, teamwork.',
    'Four of Pentacles': 'Control, security, holding tight.',
    'Five of Pentacles': 'Hardship, scarcity, isolation.',
    'Six of Pentacles': 'Generosity, fairness, exchange.',
    'Seven of Pentacles': 'Patience, assessment, long-term growth.',
    'Eight of Pentacles': 'Skill, diligence, focused work.',
    'Nine of Pentacles': 'Self-sufficiency, refinement, comfort.',
    'Ten of Pentacles': 'Wealth, legacy, stability.',
    'Page of Pentacles': 'Learning, ambition, practical curiosity.',
    'Knight of Pentacles': 'Consistency, reliability, steady progress.',
    'Queen of Pentacles': 'Nurturing, practicality, grounded care.',
    'King of Pentacles': 'Abundance, mastery, material leadership.',

    # --- Swords / Air ---
    'Ace of Swords': 'Clarity, truth, mental breakthrough.',
    'Two of Swords': 'Indecision, stalemate, blocked emotions.',
    'Three of Swords': 'Heartbreak, sorrow, emotional pain.',
    'Four of Swords': 'Rest, recovery, contemplation.',
    'Five of Swords': 'Conflict, hollow victory, discord.',
    'Six of Swords': 'Transition, moving on, healing.',
    'Seven of Swords': 'Deception, strategy, secrecy.',
    'Eight of Swords': 'Mental restriction, self-doubt.',
    'Nine of Swords': 'Anxiety, fear, sleeplessness.',
    'Ten of Swords': 'Ruin, betrayal, painful ending.',
    'Page of Swords': 'Curiosity, vigilance, new ideas.',
    'Knight of Swords': 'Action, urgency, mental intensity.',
    'Queen of Swords': 'Discernment, honesty, sharp intellect.',
    'King of Swords': 'Authority, logic, ethical judgment.'
}
