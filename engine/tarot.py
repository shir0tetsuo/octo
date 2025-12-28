
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

{
    'wands/fire': [n + ' of Wands' for n in minor_arcana], # Creativity, passion, action.
    'cups/water': [n + ' of Cups' for n in minor_arcana], # Emotions, relationships, intuition.
    'pentacles/earth': [n + ' of Pentacles' for n in minor_arcana], # Intellect, challenges, truth.
    'swords/air': [n + ' of Swords' for n in minor_arcana] # Material world, work, finances.
}
