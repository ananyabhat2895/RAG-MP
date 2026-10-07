/**
 * RAG-MP Chat Service (Retrieval-Augmented Generation for Medicinal Plants)
 * 
 * Provides isolated mock retrieval for medicinal plants and defines the contract
 * for connecting the real RAG backend.
 * 
 * ============================================================================
 * BACKEND INTEGRATION INSTRUCTIONS:
 * ----------------------------------------------------------------------------
 * Set `USE_REAL_BACKEND = true` (or configure VITE_USE_REAL_BACKEND=true in .env).
 * The service will dispatch to POST /api/rag-query.
 * 
 * Request Payload:
 * {
 *   "query": "Tell me about Ashwagandha",
 *   "history": [
 *     { "role": "user", "content": "..." },
 *     { "role": "assistant", "content": "..." }
 *   ],
 *   "project": "medicinal-plants"
 * }
 * 
 * Response Payload:
 * {
 *   "answer": "Ashwagandha (Withania somnifera) is...",
 *   "sources": [
 *     "Identification",
 *     "Botanical information",
 *     "Traditional medicine records"
 *   ]
 * }
 * ============================================================================
 */

const USE_REAL_BACKEND = false;
const BACKEND_URL = import.meta.env?.VITE_RAG_API_URL || '/api/rag-query';

const MOCK_BOTANICAL_KNOWLEDGE = [
  {
    matches: ['ashwagandha', 'withania', 'somnifera', 'indian ginseng'],
    title: 'Ashwagandha',
    answer: `Ashwagandha (*Withania somnifera*) is an evergreen shrub in the Solanaceae family native to dry subtropical parts of India.

In traditional Ayurvedic medicine, it is celebrated as a premier **Rasayana** (rejuvenative herb) indicated for balancing Vata and Kapha doshas, counteracting physical and mental stress, and enhancing vitality (*Ojas*).

Key pharmacological aspects:
• **Primary Active Compounds:** Withanolides (notably Withaferin A and Withanolide D) and alkaloids.
• **Therapeutic Actions:** Documented adaptogenic, neuroprotective, and mild anxiolytic properties.
• **Traditional Preparations:** Root powder traditionally taken with warm milk or ghee.`,
    sources: [
      'Plant Identification',
      'Botanical Information & Taxonomy',
      'Ayurvedic Pharmacopoeia of India (API), Vol. 1'
    ]
  },
  {
    matches: ['tulsi', 'botanical name of tulsi', 'holy basil', 'ocimum sanctum', 'ocimum tenuiflorum'],
    title: 'Tulsi (Holy Basil)',
    answer: `The botanical name of Tulsi is **Ocimum sanctum L.** (synonymously classified as **Ocimum tenuiflorum L.**), belonging to the Lamiaceae (mint) family.

Revered across India as the "Queen of Herbs", Tulsi holds a foundational position in Ayurvedic ethnopharmacology:
• **Phytochemical Profile:** Rich in aromatic essential oils including eugenol, carvacrol, and ursolic acid.
• **Traditional Indications:** Relieving respiratory congestion, chronic cough, seasonal fevers, and digestive discomfort.
• **Biological Activities:** Broad-spectrum antimicrobial, adaptogenic, and antioxidant activities.`,
    sources: [
      'Plant Identification & Binomial Nomenclature',
      'Flora of British India, J.D. Hooker',
      'WHO Monographs on Selected Medicinal Plants, Vol. 2'
    ]
  },
  {
    matches: ['neem vs tulsi', 'tulsi vs neem', 'compare neem and tulsi', 'difference between neem and tulsi'],
    title: 'Neem vs. Tulsi Comparison',
    answer: `While both Neem (*Azadirachta indica*) and Tulsi (*Ocimum sanctum*) are pillars of Indian traditional medicine, they differ distinctly in taxonomy, energetics, and therapeutic focus:

1. **Taxonomy & Bioactives:**
   • **Neem:** Meliaceae family; characterized by intensely bitter triterpenoid limonoids (azadirachtin, nimbin).
   • **Tulsi:** Lamiaceae family; characterized by aromatic volatile phenolic compounds (eugenol, rosmarinic acid).

2. **Therapeutic Roles:**
   • **Neem:** Cooling (*Sheetala*), purifying tonic primarily indicated for dermatological conditions, wound healing, oral hygiene, and systemic blood cleansing.
   • **Tulsi:** Warming (*Ushna*), adaptogenic respiratory tonic widely utilized for lung comfort, immune modulation, and stress resilience.`,
    sources: [
      'Comparative Ethnobotanical Survey, CCRAS',
      'Botanical Synonyms & Morphological Records',
      'Traditional Medicine Comparative Studies'
    ]
  },
  {
    matches: ['compare neem and turmeric', 'neem and turmeric', 'neem vs turmeric'],
    title: 'Neem & Turmeric Comparison',
    answer: `Neem (*Azadirachta indica*) and Turmeric (*Curcuma longa*) are frequently paired in traditional formulations for synergistic antimicrobial and anti-inflammatory therapy:

• **Neem (Margosa):** Provides cooling, bitter triterpenoids (azadirachtin) targeted at neutralizing bacterial toxins, calming inflammatory skin eruptions, and oral health.
• **Turmeric (Haridra):** Provides warming polyphenol curcuminoids that suppress COX-2 and NF-κB inflammatory pathways, supporting joint mobility and epithelial tissue repair.

Together, their combination is a staple for topical wound healing and dermatological cleansing in classical Ayurvedic treatises.`,
    sources: [
      'Plant Identification & Phytochemistry',
      'Compendium of Indian Medicinal Plants',
      'Ayurvedic Formulations & Therapeutic Indications'
    ]
  },
  {
    matches: ['neem', 'azadirachta', 'indica'],
    title: 'Neem (Azadirachta indica)',
    answer: `Neem (*Azadirachta indica*), known in Sanskrit as *Arishta* ("reliever of sickness"), is a hardy tree belonging to the mahogany family (Meliaceae).

Virtually every part of the tree—leaves, bark, seeds, and seed oil—possesses documented therapeutic applications:
• **Bioactive Limonoids:** Contains azadirachtin, nimbidin, and nimbin.
• **Clinical Focus:** Remarkable antimicrobial, antifungal, antimalarial, and anti-inflammatory properties.
• **Traditional Uses:** Dermatological disorders, chronic ulcers, periodontal care, and natural pest repellent.`,
    sources: [
      'Plant Identification',
      'The Neem Tree: Source of Unique Natural Products, H. Schmutterer',
      'WHO Monographs on Selected Medicinal Plants, Vol. 3'
    ]
  },
  {
    matches: ['turmeric', 'haldi', 'curcuma', 'longa', 'curcumin'],
    title: 'Turmeric (Curcuma longa)',
    answer: `Turmeric (*Curcuma longa*), known as *Haridra* in Sanskrit, is a perennial rhizomatous herb in the ginger family (Zingiberaceae).

Extensively utilized both as a foundational spice and therapeutic agent:
• **Primary Phytochemicals:** Curcuminoids (curcumin, demethoxycurcumin, bisdemethoxycurcumin) and volatile turmerones.
• **Mechanism of Action:** Potent antioxidant activity and direct downregulation of pro-inflammatory cytokines and enzymes (COX-2, LOX, NF-κB).
• **Traditional Uses:** Enhancing digestive metabolism (*Agni*), liver support, purifying blood, and topical wound healing.`,
    sources: [
      'Botanical Information & Rhizome Taxonomy',
      'Ayurvedic Pharmacopoeia of India, Part-I, Vol. 1',
      'Journal of Ethnopharmacology'
    ]
  },
  {
    matches: ['giloy', 'guduchi', 'tinospora', 'cordifolia', 'amrita'],
    title: 'Giloy (Tinospora cordifolia)',
    answer: `Giloy (*Tinospora cordifolia*), also known as Guduchi or *Amrita* ("nectar of immortality"), is an herbaceous climbing vine native to tropical regions of India.

In classical Ayurvedic texts, it is revered as a premier *Rasayana* and *Jvarahara* (fever reliever):
• **Key Constituents:** Diterpene lactones (tinosporaside, cordifolioside), glycosides, and immunomodulatory polysaccharides.
• **Indications:** Management of recurrent fevers, glycemic homeostasis, liver detoxification, and natural immune defense activation.
• **Biological Activities:** Increases phagocytic function and cytokine modulation in modern preclinical models.`,
    sources: [
      'Plant Identification',
      'Traditional Medicine Records',
      'Indian Journal of Medical Research'
    ]
  },
  {
    matches: ['brahmi', 'bacopa', 'monnieri'],
    title: 'Brahmi (Bacopa monnieri)',
    answer: `Brahmi (*Bacopa monnieri*), also called Water Hyssop, is a creeping wetland perennial herb in the Plantaginaceae family.

Regarded in Indian medicine as a classic **Medhya Rasayana** (nootropic herb):
• **Active Principles:** Steroidal saponins called bacosides (bacoside A and B).
• **Cognitive Benefits:** Facilitates synaptic neurotransmission, protects hippocampal neurons against oxidative damage, and fosters focus and memory retention.
• **Traditional Applications:** Mental fatigue, anxiety mitigation, and calm restorative focus.`,
    sources: [
      'Plant Identification',
      'Ayurvedic Pharmacopoeia of India, Part-I, Vol. 2',
      'Neuropsychopharmacology Literature'
    ]
  },
  {
    matches: ['ayurvedic plants', 'used in ayurveda', 'ayurveda', 'ayurvedic medicinal plants'],
    title: 'Ayurvedic Medicinal Plants',
    answer: `Ayurvedic pharmacology (*Dravyaguna Vijnana*) categorizes hundreds of botanical species based on their energetic properties: **Rasa** (taste), **Virya** (potency), and **Vipaka** (post-digestive effect).

Foundational medicinal plants widely documented include:
1. **Ashwagandha** (*Withania somnifera*) — Premier adaptogen for endurance, stress response, and rejuvenation.
2. **Tulsi** (*Ocimum sanctum*) — Sacred adaptogen and primary respiratory herbal remedy.
3. **Neem** (*Azadirachta indica*) — Potent bitter purifier for skin conditions and systemic balance.
4. **Turmeric** (*Curcuma longa*) — Fundamental anti-inflammatory rhizome supporting digestion and cellular repair.
5. **Giloy** (*Tinospora cordifolia*) — Revered immune-supportive vine for fever reduction and longevity.
6. **Amla** (*Phyllanthus emblica*) — Vitamin C-rich antioxidant cooling fruit; key base of Chyawanprash.
7. **Brahmi** (*Bacopa monnieri*) — Nootropic herb for cognitive stamina, focus, and neurological health.`,
    sources: [
      'Charaka Samhita (Sutrasthana, Ch. 4)',
      'Traditional Medicine Records',
      'Central Council for Research in Ayurvedic Sciences (CCRAS)'
    ]
  }
];

/**
 * Sends a query to the botanical retrieval engine.
 * 
 * @param {string} query - The user question
 * @param {Array<{role: string, content: string}>} [conversationHistory=[]] - Prior conversation turns
 * @param {string} [project='medicinal-plants'] - Current active workspace/project
 * @returns {Promise<{answer: string, sources: string[]}>}
 */
export async function sendMessage(query, conversationHistory = [], project = 'medicinal-plants') {
  if (!query || typeof query !== 'string' || !query.trim()) {
    throw new Error('Query must be a non-empty string');
  }

  const cleanQuery = query.trim();

  // Format history turns cleanly for backend payload
  const formattedHistory = Array.isArray(conversationHistory)
    ? conversationHistory.map(item => ({
        role: item.role || (item.sender === 'user' ? 'user' : 'assistant'),
        content: item.content || item.text || ''
      }))
    : [];

  // If real backend is toggled on:
  if (USE_REAL_BACKEND) {
    const response = await fetch(BACKEND_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: cleanQuery,
        history: formattedHistory,
        project
      })
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      throw new Error(`RAG API error (${response.status}): ${errorText || response.statusText}`);
    }

    const data = await response.json();
    return {
      answer: data.answer || '',
      sources: Array.isArray(data.sources) ? data.sources : []
    };
  }

  // --- MOCK SERVICE IMPLEMENTATION ---
  // Simulate natural search delay (550ms - 750ms)
  await new Promise(resolve => setTimeout(resolve, 600));

  const queryLower = cleanQuery.toLowerCase();

  // Match against botanical records
  const matched = MOCK_BOTANICAL_KNOWLEDGE.find(record =>
    record.matches.some(keyword => queryLower.includes(keyword))
  );

  if (matched) {
    return {
      answer: matched.answer,
      sources: matched.sources
    };
  }

  // Helpful fallback for unindexed inquiries
  const fallbackAnswer = `I searched the medicinal plant knowledge base for "${cleanQuery}".

While a fully authenticated monograph is not yet indexed for this exact phrasing in the current local reference set, RAG-MP specializes in identifying:
• **Botanical nomenclature & taxonomy**
• **Bioactive secondary metabolites** (alkaloids, flavonoids, saponins, triterpenoids)
• **Ayurvedic and ethnopharmacological citations**

You can explore detailed monographs by asking about plants like **Ashwagandha**, **Tulsi**, **Neem**, **Turmeric**, **Giloy**, or **Brahmi**, or compare traditional uses between species.`;

  return {
    answer: fallbackAnswer,
    sources: [
      'Identification',
      'Botanical information',
      'Traditional medicine records'
    ]
  };
}
