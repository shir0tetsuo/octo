ZONE_COLORS = { # Define zone colors here, zone length expands to len; Don't forget to adjust ZONE_GLYPHS
    0 : [
        '#7489c9',        '#74c9c5',        '#74bcc9',        '#74abc9',
        '#749ac9',        '#7489c9',        '#7478c9',        '#8174c9',
        '#9274c9',        '#a374c9'
    ],
    1 : [
        '#d74a49',        '#183e4b',        '#1a424f',        '#294f5b',
        '#375c67',        '#53737b',        '#6f8a90',        '#8ba0a4',
        '#bbc5c7',        '#eaeaea'
    ],
    2 : [
        '#c0decc',        '#9ccbad',        '#77b88f',        '#53a675',
        '#34b768',        '#4d9a6c',        '#3ba364',        '#478e64',
        '#3f905f',        '#41825b'
    ],
    3 : [
        '#732ff6',        '#7657eb',        '#7972df',        '#7e89d2',
        '#849dc4',        '#8bb1b3',        '#93c3a0',        '#9cd488',
        '#a5e569',        '#aff631'
    ],
    4 : [
        '#e6d1a8',        '#e6cb92',        '#e6c47c',        '#e0ba6a',
        '#d7ae5b',        '#cea34c',        '#c5983c',        '#ba8e32',
        '#ab8538',        '#9c7c3c',        '#8c6c30'
    ],
    5 : [
        '#1F1A2B',        '#211735',        '#250F46',        '#362A55',
        '#4F3A87',        '#5828A6',        '#5F10B8',        '#7434E0',
        '#782AEA',        '#7C17F4'
    ],
    6 : [
        "#3C1003",        "#5F2D10",        "#8B4117",        "#BC7A17",
        "#E6582D",        "#FF7741",        "#FF906E",        "#FFA9A9",
        '#FFD3D9'
    ],
    7 : [
        '#98dadb',        '#98c8e5',        '#98b6ee',        '#a5ade7',
        '#bdadd1',        '#d4acba',        '#e6a48f',        '#dfc090',
        '#d5db90',        '#c2dea3',        '#accac3'
    ],
    8 : [
        '#845A6D',        '#613A4B',        '#3E1929',        '#564769',
        '#6E75A8',        '#7E83B8',        '#8D91C7',        '#9FB6DC',
        '#A8C8E7',        '#B0DAF1'
    ],
    9 : [
        '#d9ed92',        '#b5e48c',        '#99d98c',         '#76c893', 
        '#52b69a',        '#34a0a4',        '#168aad',         '#1a759f', 
        '#1e6091',        '#184e77'
    ],
    10 : [
        '#03071e',        '#370617',        '#6a040f',         '#9d0208',
        '#d00000',        '#dc2f02',        '#e85d04',         '#f48c06',
        '#faa307',        '#ffba08'
    ],
    11 : [
        '#d9ed92',        '#b5e48c',        '#99d98c',         '#76c893', 
        '#52b69a',        '#34a0a4',        '#168aad',         '#1a759f', 
        '#b185db',        '#a06cd5',        '#9163cb',         '#815ac0',
    ],
    12 : [
        '#641220',        '#6e1423',        '#85182a',         '#a11d33',
        '#a71e34',        '#b21e35',        '#bd1f36',         '#c71f37',
        '#da1e37',        '#e01e37'
    ],
    13 : [
        '#ffe169',        '#fad643',        '#edc531',         '#dbb42c',
        '#c9a227',        '#b69121',        '#a47e1b',         '#926c15',
        '#805b10',        '#76520e'
    ],
    14 : [
        '#dec9e9',        '#dac3e8',        '#d2b7e5',         '#c19ee0',
        '#b185db',        '#a06cd5',        '#9163cb',         '#815ac0',
        '#7251b5',        '#6247aa'
    ],
    15 : [
        '#e4a5ff',        '#deabff',        '#d8b1ff',         '#cbbdff',
        '#c5c4ff',        '#bfcaff',        '#b8d0ff',         '#b2d6ff',
        '#d1b7ff',        '#acdcff'
    ]
}

ZONE_INTEGERS = list(range(0, len(ZONE_COLORS)))
'''List int of Database, where last integer is n zones.'''

# https://en.wikipedia.org/wiki/List_of_Egyptian_hieroglyphs
ZONE_GLYPH_TABLES = { # 8 Zones, but (this is spread "evenly" among the zones. Keep that in mind.)
    'birds': [
        '𓄿','𓅀','𓅱','𓅷','𓅾','𓅟','𓅮','𓅙','𓅰','𓅚',
        '𓅞','𓅪','𓅜','𓅛','𓅘','𓅓','𓅔','𓅃','𓅂'
    ],
    'sea': [
        '𓆛','𓆜','𓆝','𓆞','𓆟','𓆡','𓆠','𓅻','𓈖','𓆢'
    ],
    'jackals': [
        '𓃢','𓃦','𓃥','𓃣','𓁢','𓃤','𓃧','𓃨'
    ],
    'misc': [
        '𓇌','𓆝','𓍝','𓇋','𓃣','𓍚','𓏢','𓐤','𓌬','𓆣','𓆥',
        '𓆏','𓆋','𓄇','𓃕','𓆉','𓅱'
    ],
    'reptiles': [
        '𓆈','𓆉','𓆊','𓆌','𓆏','𓆇','𓆑','𓆓','𓆗','𓆙',
        '𓆚','𓆘'
    ],
    'deities': [
        '𓁛','𓁠','𓁦','𓁥','𓁮','𓁭','𓁩','𓁳','𓁴','𓁧','𓁨',
        '𓁱','𓁣','𓁚','𓁫','𓁟','𓁢','𓁵','𓁜','𓇴'
    ],
    'man': [
        '𓀝','𓀓','𓀗','𓀞','𓀀','𓀃','𓀊','𓀋','𓀏','𓀦','𓀛'
    ],
    'animal': [
        '𓃒','𓃓','𓃔','𓃕','𓃗','𓃘','𓃙','𓃚','𓃜','𓃝',
        '𓃟','𓃠','𓃡','𓃢','𓃣','𓃥','𓃩','𓃫','𓃬','𓃭',
        '𓃯','𓃰','𓃱','𓃲','𓃴','𓃶','𓃷','𓃹','𓃺','𓃻',
        '𓆤'
    ],
    'woman': [
        '𓁐','𓁑','𓁘','𓁦','𓏏','𓆘','𓅒'
    ],
    'charm': [
        '𓆭','𓆮','𓆯','𓆰','𓆱','𓆲','𓆸','𓇅','𓇆','𓇇','𓇈',
        '𓇉','𓇌','𓇋','𓇍','𓇎','𓇏','𓇐','𓇓','𓇑','𓇒','𓇗','𓇘',
        '𓇙','𓇬','𓇭','𓋹'
    ],
    'boundary': [
        '𓉥','𓉔','𓉒','𓉑','𓈗','𓈈','𓇽'
    ]
        
}

ZONE_GLYPHS = { # 8 Zones
    0 : [
        *ZONE_GLYPH_TABLES['birds']
    ],
    1 : [
        *ZONE_GLYPH_TABLES['jackals'],
        *ZONE_GLYPH_TABLES['sea']
    ],
    2 : [
        *ZONE_GLYPH_TABLES['reptiles'],
        *ZONE_GLYPH_TABLES['sea'],
    ],
    3 : [
        *ZONE_GLYPH_TABLES['misc']
    ],
    4 : [
        *ZONE_GLYPH_TABLES['jackals'],
        *ZONE_GLYPH_TABLES['deities']
    ],
    5 : [
        *ZONE_GLYPH_TABLES['jackals'],
        *ZONE_GLYPH_TABLES['reptiles']
    ],
    6 : [
        *ZONE_GLYPH_TABLES['sea'],
        *ZONE_GLYPH_TABLES['birds'],
        *ZONE_GLYPH_TABLES['deities'],
        *ZONE_GLYPH_TABLES['boundary']
    ],
    7 : [
        *ZONE_GLYPH_TABLES['misc'],
        *ZONE_GLYPH_TABLES['reptiles']
    ],
    8 : [
        *ZONE_GLYPH_TABLES['man'],
        *ZONE_GLYPH_TABLES['deities']
    ],
    9 : [
        *ZONE_GLYPH_TABLES['sea'],
        *ZONE_GLYPH_TABLES['animal'],
        *ZONE_GLYPH_TABLES['woman']
    ],
    10 : [
        *ZONE_GLYPH_TABLES['charm'],
        *ZONE_GLYPH_TABLES['man'],
        *ZONE_GLYPH_TABLES['jackals']
    ],
    11 : [
        *ZONE_GLYPH_TABLES['man'],
        *ZONE_GLYPH_TABLES['woman'],
        *ZONE_GLYPH_TABLES['birds']
    ],
    12 : [
        *ZONE_GLYPH_TABLES['woman'],
        *ZONE_GLYPH_TABLES['man'],
        *ZONE_GLYPH_TABLES['animal']
    ],
    13 : [
        *ZONE_GLYPH_TABLES['charm'],
        *ZONE_GLYPH_TABLES['birds'],
        *ZONE_GLYPH_TABLES['woman']
    ],
    14 : [
        *ZONE_GLYPH_TABLES['birds'],
        *ZONE_GLYPH_TABLES['deities'],
        *ZONE_GLYPH_TABLES['woman']
    ],
    15 : [
        *ZONE_GLYPH_TABLES['birds'],
        *ZONE_GLYPH_TABLES['jackals'],
        *ZONE_GLYPH_TABLES['charm'],
        *ZONE_GLYPH_TABLES['woman']
    ]
}
