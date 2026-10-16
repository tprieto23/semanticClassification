# Codebook for Semantic Entity Extraction and Labeling

**Status:** Operational draft for review; pilot not yet approved.

**Version:** Draft 0.2 — October 16, 2026.

Extract literal mentions and classify them into the 10 categories in this codebook. Use the instructions and the text provided; do not consult external documents or add information from external knowledge. Applying the codebook to the corpus requires the pilot review described in section 10.

## 1. Purpose of Annotation

### 1.1. Immediate Objective

Identify words or short spans present in the text and assign them the corresponding labels from the system of 10 categories.

### 1.2. Expected Result

Produce classified mentions linked to their source documents and sentences. For example, a mention of “Wyss” that identifies the actor receives the `CHAR` label.

### 1.3. Subsequent Use and Final Objective

Processing is organized into three consecutive tasks, executed through independent endpoints:

1. **NER:** extract literal mentions and classify them into the 10 categories.
2. **Fuzzy matching:** normalize and group variants through entity resolution, preserving the original mentions and their evidence.
3. **Relationship construction:** connect the consolidated entities based on the co-occurrence of their mentions to build a semantic network.

Each task requires the previous one to be completed. This codebook defines NER extraction and classification. Preserve the original mentions; normalization, entity resolution, and relationship construction are performed in the subsequent tasks.

### 1.4. Operational Role within the API

The codebook is the methodological reference for the prompt, classification criteria, and NER annotation contract. Its rules must be incorporated into the prompt and code checks; the API does not automatically include this entire document.

The model returns classified mentions through the `label`, `text`, `sentence_id`, and `ambiguity` fields. The code calculates their positions and preserves the source sentence as context. NER provides this evidence for the subsequent tasks; its responsibility is limited to extraction and classification.

## 2. Domain and Scope

### 2.1. Thematic Framework

Nature conservation, sustainable living, and territorial governance in the Peruvian Amazon.

This framework encompasses the ecological, social, economic, cultural, and institutional components of the territory and their interactions concerning the use, conservation, and transformation of ecosystems and the living conditions of populations.

### 2.2. Focus

Deforestation and social-ecological transitions.

### 2.3. Scope Criteria

Deforestation and social-ecological transitions provide a thematic orientation. Including a mention does not require its sentence to explicitly name deforestation or a social-ecological transition. Its relevance is determined by the connection that the text and its context establish with the territorial system covered by the thematic framework and by the criteria of the 10 annotation categories.

- Role of the focus: thematic orientation.
- NER input: clean text from `.txt` files; its entire content is processed in chunks. Uploading and converting other formats are earlier stages.
- Supported languages: any language; preserve spans in their original language.
- Included content: relevant mentions of the ecological, social, economic, cultural, and institutional components of the territorial system, including practices, actors, places, rules, infrastructure, knowledge, attitudes, and capabilities, according to the 10 categories. Markets, migration, and other processes may be included when they meet these criteria, even if the sentence does not explicitly mention deforestation.
- Formats excluded from NER: files that have not yet been converted and cleaned into text.

### 2.4. Territorial and Thematic Context of the Corpus

The codebook guides the extraction of mentions in texts about the social-ecological systems of the Peruvian Amazon. The aim is to understand how ecosystems, populations, productive and extractive activities, and forms of territorial organization and management relate to one another in connection with nature conservation, living conditions, and territorial transformations.

This context includes the use and transformation of forests and other ecosystems; productive and extractive practices; conservation and restoration; access to infrastructure and markets; and the living conditions of populations. It also encompasses land tenure and territorial rights, participation and coordination among actors, local and technical knowledge, identities and values, and the capabilities needed to manage the territory.

### 2.5. Conceptual Guidelines for Extraction

#### 2.5.1. Coverage of the Social-Ecological System

**Conceptual basis:** The territory is understood as a social-ecological system in which ecological, social, economic, cultural, and institutional components interact. Understanding it requires recognizing both conservation and regeneration dynamics and extraction, degradation, and conflict dynamics, together with the conditions that enable or limit them.

**Operational guideline:** Extraction must identify relevant mentions of these components when they are supported by the text and meet the criteria of one of the 10 categories. Inclusion is determined by their relevance to the domain and their contextual function. Mentions presented as favorable, unfavorable, or ambivalent may all be annotated.

**Conceptual example:** In a passage about roads, mining, communities, and conservation, each expression is assessed according to its context and the category criteria. Selection is not limited to expressions associated with desirable outcomes.

#### 2.5.2. Classification According to the Mention's Contextual Function

**Conceptual basis:** An area of the territorial system may bring together actors, rules, practices, support structures, knowledge, and other components. A passage about governance may mention organizations, institutional instruments, and management processes. Each mention may belong to a different category.

**Operational guideline:** Classify each mention according to the component it identifies and the function that the text attributes to it in context, applying the definitions and criteria of the 10 categories. The passage topic, section title, and indicative words may guide interpretation; the assignment must be supported by the mention and its context.

**Illustrative examples:** “SERNANP,” presented as a participating organization, corresponds to an actor (`CHAR`); a “master plan,” presented as a management instrument, corresponds to a rule or instrument (`RUL`); “land titling for native communities,” presented as a process, corresponds to a practice (`PRAC`).

When the function cannot be determined using the permitted context, apply the ambiguity policy in section 7.

## 3. Annotation Units and Context

- Meaning of entity or mention in this task: a word or short span of text that identifies a component of the territory classifiable into one of the 10 categories.
- Unit receiving a label: a continuous, literal span that is sufficiently complete to identify what is mentioned and is contained within one sentence.
- Permitted context for interpreting a mention: the sentence containing the mention and the other sentences in the chunk received by the model. The source sentence is saved as context.
- Required textual evidence and permitted inferences: every annotation must be supported by the text. Do not add entities or attributes using external knowledge.
- Handling repeated mentions: record each occurrence as an independent mention, with its position and context (section 6.2). Subsequent linking to the same canonical node preserves this evidence.
- Distinction between a literal mention and a canonical entity: extraction preserves the literal text of the selected span; normalization and linking to canonical entities belong to the subsequent fuzzy matching task.
- Scope of this stage: NER extracts and classifies mentions. Relationship construction and its co-occurrence rules are defined in the network task.

## 4. Label System

- Number of categories: 10.
- Label set: fixed to the 10 codes in the following table.
- One or more labels for the same span: assign the category corresponding to its contextual function. A LOC span may be annotated inside a CHAR span according to section 6; these are two distinct spans.
- Handling expressions that do not belong to any category: omit them without forcing a classification.

Use the labels exactly as shown in the table, preserving uppercase, lowercase, and underscores.

| Code | Category |
|---|---|
| CHAR | Actors |
| KNOW | Knowledge |
| ATT | Attitudes and values |
| SKILL | Skills |
| PRAC | Practices |
| physical_INFRA | Physical infrastructure |
| soft_INFRA | Support infrastructure |
| eco_INFRA | Ecological infrastructure |
| RUL | Rules |
| LOC | Places |

## 5. Operational Definitions by Category

Classify each mention by applying:

- Operational definition and essential characteristics.
- Inclusion and exclusion criteria.
- Textual evidence required to assign the label.
- Distinction from neighboring categories.

### 5.1. CHAR — Actors

**Definition:** An individual or collective actor that the text identifies as a participant in the territorial system, with agency, responsibility, representation, rights, interests, or experience of impacts related to its social-ecological processes. An individual actor is a person; a collective actor may be a human group, community, people, or organization.

**Characteristics the mention must identify:**

1. A person, human group, community, people, or organization.
2. An explicit designation of the actor, through a proper name, position, occupation, or generic expression.
3. A role supported by the context in the territorial system: agency, responsibility, representation, rights, interests, or experience of impacts related to its social-ecological processes.

**Inclusion criteria:**

- Individual and collective actors are allowed, whether named or generic.
- Include affected actors even when they do not perform an action.
- Include actors whose participation in an activity is negated; preserve that negation in context without asserting participation.

**Exclusion criterion:** An expression that only locates a process or event, without identifying the collective as an actor in context, does not receive CHAR. In “The workshop took place in the community of San Pedro,” record only “San Pedro” as LOC.

**Required evidence:** The designation and its context must identify the actor and its territorial role. Neither a proper name nor the performance of an action is required. Use the context permitted in section 3.

**Category boundaries:**

- LOC identifies the place; CHAR identifies the person or collective. LOC is allowed inside CHAR when both identifications are supported by the context, according to section 6.1.
- RUL identifies the rule or instrument; CHAR identifies the actor that establishes or applies it. The contextual criterion for plans is in section 5.9.
- PRAC identifies the activity; CHAR identifies the actor. “Community monitoring” identifies a practice in the example in section 5.5.

**Examples:**

- “The association of producers from Tambopata participates in the project”: “association of producers from Tambopata” identifies a collective actor.
- “The farmers in the area participate in the project”: “farmers in the area” identifies a collective actor through a generic designation.
- “River pollution affects the riverside communities”: “riverside communities” identifies an affected collective actor, even if it does not perform an action.
- “The municipality approved the forest management plan”: “municipality” identifies a collective actor. The classification of “the forest management plan” is assessed using the contextual criterion in section 5.9; mentioning its approval alone does not specify the conditions, responsibilities, or criteria it establishes.

The examples illustrate classification characteristics; the rules on pronouns, articles, proper names, acronyms, and enumerations are collected in section 6.3.

### 5.2. KNOW — Knowledge

**Definition:** Technical, ecological, or traditional knowledge about the territory, its ecosystems, and their management.

- **Technical knowledge:** Knowledge about techniques, methods, tools, or procedures, such as knowledge of soil management or agroforestry systems.
- **Ecological knowledge:** Knowledge about ecosystems, species, cycles, and ecological relationships, such as knowledge of Brazil nut flowering.
- **Traditional knowledge:** Local or Indigenous knowledge that is preserved or transmitted, such as knowledge of plant uses or traditional forest management.

These types are descriptive references within KNOW; they are not new category codes.

**Inclusion criterion:** The text must identify knowledge or knowledge content. It may do so through an explicit designation, such as “traditional knowledge of forest management,” or through an expression attributing knowledge, such as “the producers know the Brazil nut flowering cycles.” Extract “Brazil nut flowering cycles” as KNOW and “producers” as CHAR.

**Knowledge holder:** Explicit mentions of knowledge are allowed even when the text does not identify who holds it. This does not authorize attributing a holder that the text does not identify.

**Handling general statements:** Assign KNOW only when the text identifies the content as knowledge or attributes knowledge. An informative statement or a description of the territory is not sufficient on its own to assign KNOW. Identifying the knowledge holder is not required.

**Evidence and exclusions:** The presence of a practice, skill, or technical term alone does not show that the text is describing knowledge. Performing an activity does not automatically justify adding a KNOW annotation. A statement about the territory must be assessed in context to determine whether it presents knowledge content according to this definition.

**Distinction:** KNOW identifies knowledge or known content; SKILL identifies competence to perform a task; PRAC identifies the activity.

**Boundary with ATT:** Evaluations, identities, and commitments are assessed under ATT. Each category requires its own evidence.

**Examples distinguishing KNOW, SKILL, and PRAC:**

| Text | Illustrative interpretation |
|---|---|
| The women producers know the Brazil nut flowering cycles. | KNOW: expresses ecological knowledge. |
| The women producers know how to use monitoring equipment. | SKILL: expresses operational competence. |
| The women producers monitor Brazil nut flowering. | PRAC: expresses an activity. |

- Exclusions: an isolated activity, skill, or technical term is not sufficient to assign KNOW.
- Boundary with ATT: KNOW identifies knowledge or known content; ATT identifies evaluations, perceptions, identities, and commitments.
- General statements: a description of the territory does not automatically receive KNOW. The text must present it as knowledge or knowledge content.
- Span: extract the content of the knowledge, preserving in context the expression that identifies it as such.

### 5.3. ATT — Attitudes and Values

**Definition:** Values, identities, perceptions, and commitments that the text attributes to individual or collective actors regarding the territory, its ecosystems, or their management.

**Inclusion and evidence:** Assign ATT when the text expresses an evaluation, perception, identity, or commitment and attributes it to an individual or collective actor.

**Exclusion:** A factual description, knowledge, or the performance of an activity is not sufficient on its own to assign ATT.

**Range:** Include favorable, unfavorable, or ambivalent attitudes toward the territory, its ecosystems, or their management.

**Span:** Extract the expression identifying the attitude and what it refers to, preserving the actor and the attribution in context.

**Illustrative examples:** Sense of belonging, appreciation of the forest, and commitment to its conservation.

**Distinction:** Evaluating or perceiving corresponds to ATT; knowing corresponds to KNOW; acting corresponds to PRAC. Do not infer an attitude solely because someone performs an activity.

**Annotation example:** In “The women producers express their commitment to forest conservation,” extract “commitment to forest conservation” as ATT and “women producers” as CHAR.

### 5.4. SKILL — Skills

**Definition:** Skills or competencies that the text attributes to individual or collective actors for performing technical, management, or monitoring tasks in the territory.

**Types of skills:** Technical, management, and monitoring.

**Inclusion and evidence:** Assign SKILL when the text attributes to an actor a skill or competence to perform a technical, management, or monitoring task.

**Exclusion:** Knowing a technique, wanting to apply it, or performing an activity does not, on its own, demonstrate a skill.

**Operational capability:** Distinguish competence to do something from having permission, resources, or an opportunity to do it. The word “can” alone is not sufficient to assign SKILL.

**Span:** Extract the expression identifying the skill and the corresponding task, preserving the actor and the attribution in context.

**Illustrative examples:** Ability to operate equipment, manage projects, or apply restoration techniques.

**Distinction:** Knowing a technique corresponds to KNOW; knowing how to apply it corresponds to SKILL; applying it corresponds to PRAC. Performing an activity is not sufficient on its own to annotate a skill.

**Annotation example:** In “The women producers have the ability to operate monitoring equipment,” extract “ability to operate monitoring equipment” as SKILL and “women producers” as CHAR.

### 5.5. PRAC — Practices

**Definition:** Activities, routines, or processes that the text identifies for producing, using, conserving, restoring, monitoring, marketing, or managing components of the territory.

**Activities covered:** Agroforestry, monitoring, marketing, restoration, and governance as an activity or process.

**Inclusion and evidence:** Assign PRAC when the text names an activity or describes a specific action relevant to the territory. It may be expressed as a noun or a verb phrase. Identifying the actor is not required when the activity is explicit.

**Exclusion:** An actor, support structure, rule, body of knowledge, or skill does not, on its own, constitute a practice. Do not annotate generic verbs such as “improve,” “strengthen,” or “promote”; if they accompany a specific activity, extract the expression identifying that activity.

**Range:** Practices may be sustainable, degrading, or ambivalent.

**Existing, proposed, or negated activities:** Extract explicit activities even when they are presented as proposed, future, necessary, or negated. Preserve that status in context; the annotation identifies the activity without asserting that it has been performed. A general desire or objective without an identifiable activity is not sufficient to assign PRAC.

**Span:** Extract the activity designation or the minimal verb phrase identifying it. Preserve its necessary complements and literal form without converting verbs to the infinitive or reconstructing omitted words.

**Distinction:** Knowing how to perform an activity corresponds to SKILL; the activity corresponds to PRAC; the norms regulating it correspond to RUL.

**Annotation examples:**

- In “Community monitoring activities are carried out,” extract “Community monitoring” as PRAC. The modifier “Community” does not, on its own, name an actor and is not sufficient to add CHAR.
- In “Forest restoration is proposed,” extract “Forest restoration” as PRAC; preserve the proposal in context without asserting its implementation.

### 5.6. physical_INFRA — Physical Infrastructure

**Definition:** Material elements that are built or installed and enable or condition access, mobility, energy supply, or technological connectivity in the territory.

**Examples:** Roads, bridges, ports, electricity networks, and telecommunications antennas.

**Inclusion and evidence:** Assign physical_INFRA when the element's designation and its context identify a built or installed structure with one of these functions. The function may be expressed in the designation itself or described in context.

**Exclusion:** An object's material nature is not sufficient. Equipment, a building, or a facility does not automatically receive physical_INFRA because it is physical. Activities of building, maintaining, or using it are not classified here, nor are natural structures classified here for their ecological function.

**Span:** Extract the element's designation, including its proper name and the modifiers needed to identify it. Preserve the literal text; activities performed on it are assessed separately as PRAC.

**Distinction:** The road corresponds to physical_INFRA; its construction or maintenance corresponds to PRAC. Classification depends on the described function, not solely on its being a physical object.

**Boundary with soft_INFRA:** Distinguish according to the described function: physical_INFRA covers access, mobility, energy, or technological connectivity; soft_INFRA covers the organized support structures defined in its category description. The presence of material components does not determine the label on its own.

**Monitoring equipment:** If the text presents it as an organized resource for monitoring, assess it as soft_INFRA. If it describes a structure for technological connectivity, assess it as physical_INFRA. The word “equipment” alone does not resolve the category.

**Annotation example:** In “The bridge provides access to the territory,” extract “bridge” as physical_INFRA.

### 5.7. soft_INFRA — Support Infrastructure

**Definition:** Systems, facilities, and organized resources that support production, learning, monitoring, or information management in the territory.

**Examples:** Nurseries, seed banks, monitoring systems, and digital platforms.

**Inclusion and evidence:** Assign soft_INFRA when the text identifies a system, facility, or organized resource and its support function for these activities. The function may be expressed in the designation or described in context; merely mentioning resources without that function is not sufficient.

**Exclusion:** An activity, body of knowledge, competence, organization, or rule does not, on its own, constitute support infrastructure. Distinguish the support structure from the activity it enables, the actor managing it, and its usage rules.

**Functional criterion:** These support structures may have material components; their support function matters, not solely their material nature.

**Span:** Extract the support structure's designation with the modifiers needed to identify its function, such as “monitoring system” or “seed bank.” Preserve the literal text and proper names.

**Distinction from PRAC:** The monitoring system corresponds to soft_INFRA; carrying out monitoring corresponds to PRAC.

**Boundary with physical_INFRA:** Nurseries, seed banks, and equipment organized for monitoring correspond to soft_INFRA because of their support function. Structures for access, mobility, energy, or technological connectivity are assessed as physical_INFRA.

**Boundary with eco_INFRA:** Primary forest and corridors are assessed as eco_INFRA when they perform ecological functions. The function described in context determines the classification.

**Annotation example:** In “The seed bank preserves material for plant production,” extract “seed bank” as soft_INFRA.

### 5.8. eco_INFRA — Ecological Infrastructure

**Definition:** Natural or restored ecological structures that support ecosystem functions, ecological connectivity, resilience, biodiversity, or territorial regeneration.

**Examples:** Primary forests, biological corridors, and wetlands.

**Inclusion and evidence:** Assign eco_INFRA when the text identifies an ecological structure and supports its ecosystem, connectivity, resilience, biodiversity, or regeneration function. Its natural character or name alone is not sufficient; do not attribute functions using external knowledge.

**Exclusion:** An event's location, a territorial boundary, or the mention of a place does not, on its own, demonstrate an ecological function. Activities of conserving, restoring, or managing a structure are assessed as PRAC. Organized support structures for producing plants or monitoring are assessed as soft_INFRA.

**Span:** Extract the ecological structure's designation, preserving the modifiers and proper names needed to identify it. The explanation of its function remains in context.

**Distinction:** The structure in its ecological function corresponds to eco_INFRA; the space in terms of location or boundaries corresponds to LOC; conserving or restoring it corresponds to PRAC.

**Boundary with soft_INFRA:** Primary forest and corridors are assessed as eco_INFRA when the text supports their ecological functions. A nursery or seed bank is classified according to its support function for production, even if it contributes to restoration.

**Annotation and boundary examples:**

- In “Wetlands regulate water and support biodiversity,” extract “Wetlands” as eco_INFRA.
- In “The workshop took place in the wetland,” “wetland” identifies the event's location and corresponds to LOC; that sentence does not support eco_INFRA.

### 5.9. RUL — Rules

**Definition:** Norms, instruments, or agreements that establish rights, obligations, permissions, or criteria to guide decisions, participation, and practices in the territory.

**Examples:** Laws, ordinances, policies, community agreements, certification standards, and participation mechanisms.

**Inclusion and evidence:** Assign RUL when the text identifies a rule or presents an instrument or agreement with a regulatory function: establishing rights, obligations, permissions, conditions, or criteria for territorial decisions and practices. A generic designation such as “agreement,” “plan,” or “mechanism” alone is not sufficient without that function.

**Formality:** Include legal, institutional, or community rules, whether formal or informal, when their regulatory function is supported by the text. Verifying their recognition in external sources is not required.

**Exclusion:** A desire, preference, or personal commitment does not, on its own, constitute a rule. Distinguish the norm from the organization establishing it, the support structure enabling its application, and the activity of developing or implementing it.

**Span:** Extract the designation of the norm, instrument, or agreement, preserving the name, number, and modifiers needed to identify it. If it has no designation, extract the minimal expression stating the right, obligation, permission, or prohibition. Preserve negation when it is part of the rule's content.

**Distinction:** The rule corresponds to RUL; the actor establishing or applying it corresponds to CHAR; the activity of applying it corresponds to PRAC.

**Inclusion criterion — plans:** Include plans in RUL when the context presents them as instruments establishing conditions, responsibilities, or criteria for territorial practices. The designation “plan” alone is not sufficient to assign RUL; the text and its context must support that function.

This criterion classifies the mention of the plan as an instrument. Its prescriptions and the activities of developing or implementing it must be distinguished from that mention and assessed according to their categories.

**Annotation example:** In “The forest management plan establishes responsibilities,” extract “forest management plan” as RUL.

### 5.10. LOC — Places

**Definition:** Geographic, territorial, administrative, or ecological spaces or units that the text identifies through their location, extent, or boundaries.

**Examples:** Indigenous territories, communities as places, reserves, watersheds, protected areas, and intervention zones.

**Inclusion and evidence:** Assign LOC when the text names a space or territorial unit or identifies it through its location, extent, or boundaries. Allow proper names and generic designations when the context makes their spatial referent recognizable; a place name is not required.

**Exclusion:** A person, collective, or organization does not receive LOC because of its connection to a territory. A structure described through its ecological function is assessed as eco_INFRA. Do not add geographic information or reconstruct names or boundaries that do not appear in the text.

**Span:** Extract the place designation with the terms needed to identify its geographic unit, such as “Tambopata River basin.” Preserve complete proper names and their constituent articles. Omit external prepositions that merely introduce the location, such as “in” or “toward.”

**Distinction:** The community as a collective corresponds to CHAR; its territory corresponds to LOC. A forest as a geographic space corresponds to LOC; as a structure supporting ecological functions, it corresponds to eco_INFRA.

**Annotation within CHAR:** In “The community of San Pedro decided to participate,” annotate “San Pedro” as LOC inside the span “community of San Pedro,” annotated as CHAR without the initial article. See section 6.

**Location example:** In “The workshop took place in the community of San Pedro,” record only “San Pedro” as LOC. In that context, the collective is not identified as an actor.

**Nesting and context:** In both examples above, the LOC span is “San Pedro.” The additional CHAR annotation requires the text to identify the collective as an actor. Do not add CHAR solely because an event takes place in a community.

## 6. General Annotation Rules

- **Literal wording and length:** extract a word or the minimal complete continuous span that identifies the component, within a single sentence. Preserve language, capitalization, accents, plural forms, and verb forms. Do not translate, lemmatize, complete omitted words, or rephrase the sentence.
- **Span boundaries:** include proper names, numbers, descriptors, and modifiers needed to identify the component and its function. Leave explanations, circumstances, and attributions in context; apply the specific rules in the category descriptions, such as the attitude with its object and the skill with its task. Do not extract a complete explanatory sentence if a shorter expression identifies what is mentioned. In PRAC, preserve the activity with its necessary object and leave separable actors, locations, and support structures in context; a product or residue does not, on its own, constitute a practice. In KNOW, extract the content of the knowledge without including an entire explanation.
- **Articles and punctuation:** omit external articles introducing the designation, introductory prepositions, and external punctuation. Preserve articles, prepositions, and punctuation that are part of the name or expression. In CHAR, preserve the descriptor identifying the actor alongside its name, as in “cooperative La Esperanza” (section 6.3).
- **Acronyms and abbreviations:** extract the explicit form when its context supports a category. If the full name and acronym appear, record both separately. Do not invent expansions or resolve identities.
- **Enumerations:** record each explicit designation separately in any category. Where words are omitted or modifiers are shared, preserve only continuous spans identifiable in context. Do not copy a modifier to another position or reconstruct complete designations.
- **References:** do not annotate pronouns or empty references such as “this” or “there,” or replace them with their antecedents. Generic designations are allowed if they meet their category criteria.
- **One category per occurrence:** choose the function best supported by the context, using the category boundaries in the category descriptions and section 7. The same word may receive different categories in different occurrences.
- **Nesting and overlaps:** allow only LOC strictly contained within CHAR, with evidence for both (section 6.1). Do not generate other nested spans, partial overlaps, or discontinuous spans. Preserve the minimal complete expression of the main component; its internal words do not constitute additional annotations. For example, within ATT “commitment to forest conservation,” do not add an internal PRAC “forest conservation.”
- **Negation and temporality:** an explicit mention may be preserved even when it is negated, absent, proposed, hypothetical, future, or obligatory, provided it meets the category criteria. The annotation does not assert existence, possession, or implementation. Preserve that status in context; include negation in the span when it is part of a RUL prescription. Do not add polarity or time fields or infer KNOW, ATT, or SKILL from an activity or intention.
- **Repetitions:** record each occurrence with its position and context, including within the same sentence (section 6.2).
- **Subsequent stages:** preserve each mention's text and category. Grouping variants, resolving identities, discrepancies between nodes, and relationships belong to fuzzy matching and network construction; they are outside NER instructions.

### 6.1. Annotating LOC within CHAR

A span identifying a place (LOC) may be annotated inside another identifying an actor (CHAR) when the text and its context support both identifications. Each annotation preserves its own span and category.

**Example:** “The community of San Pedro decided to participate.”

| Span | Category | Referent |
|---|---|---|
| community of San Pedro | CHAR | The collective that decided to participate; the initial article is omitted. |
| San Pedro | LOC | The place identified in the collective's designation. |

**Contextual limit:** In “The workshop took place in the community of San Pedro,” record only “San Pedro” as LOC. The expression only locates the workshop; it is not sufficient to add CHAR. The presence of a place name inside the expression does not automatically trigger two annotations.

Nesting allows the two spans in the example “The community of San Pedro decided to participate,” with one contained within the other. It does not allow assigning two labels to the same interval or generalizing nesting to other combinations. The implications for canonicalization and co-occurrence counting belong to their subsequent stages.

### 6.2. Recording Repeated Mentions

Record each occurrence of a mention as an independent annotation, with its position in the document and its context. Repetition of the same text does not remove subsequent occurrences.

**Example:** If “women cacao producers” appears in three sentences, preserve three mentions, each linked to its position and context. They may subsequently be linked to the same canonical node without losing the three pieces of evidence.

The code calculates positions and context according to section 8. The model records occurrences in textual order so that local searching assigns successive positions. The four-field contract does not distinguish which occurrence was intended if identical text is repeated in the same sentence and only some occurrences are annotated; these cases require pilot review. Co-occurrence counting or weighting rules are defined in the network stage.

### 6.3. Extracting CHAR Mentions

**Evidence and exclusion criterion — pronouns:** For CHAR, extract only expressions that name the actor, whether through a proper name, position, occupation, or collective designation. Pronouns referring to an actor are not annotated as CHAR, even when their referent is clear in context. This preserves the inclusion of generic designations; a proper name is not required.

**Example:** In “The farmers participate in monitoring. They record changes in the forest,” annotate “farmers” as CHAR and do not annotate “They” as CHAR. Do not replace the pronoun with a new mention of “farmers” in the second sentence.

**Span boundary — initial article:** Omit the article introducing the actor's designation. In “The women cacao producers participated in the workshop,” annotate “women cacao producers” as CHAR, leaving out “The” and preserving “cacao.” Articles that are part of a proper name are preserved according to the following criterion; the general span boundary rules at the beginning of section 6 apply.

**Complete proper name — criterion:** Preserve the actor's complete proper name, including its constituent articles. “La Esperanza” is a proper name and remains intact: do not remove “La” or extract it as a separate annotation. Omitting the article that introduces a designation does not authorize removing an article that is part of the name.

**Span:** In “The cooperative La Esperanza participated in the workshop,” extract “cooperative La Esperanza” as CHAR. Include “cooperative” and preserve the complete name “La Esperanza.” Include descriptors identifying the actor; leave additional explanations in context.

**Preserving the span:** Once the mention's boundaries are set, preserve the text as it appears. In the women producers example, extract “women cacao producers,” preserving the plural. Normalization belongs to a subsequent stage and does not replace the original extracted span.

**Full name and acronym — extraction:** When an actor's full name and acronym appear explicitly, extract them as two independent CHAR records, each with its literal span, position, and context.

**Example:** In “The Asociación de Productores de Cacao (APC) participated in the workshop,” extract separately:

- “Asociación de Productores de Cacao” → CHAR.
- “APC” → CHAR.

**Canonicalization for the example:** The two mentions are subsequently linked to the same canonical node because the text presents “APC” as the acronym of “Asociación de Productores de Cacao.” Preserve both original records with their positions and context.

Matching acronyms alone does not establish identity between actors. NER classifies the observed form with its context and ambiguity; identity resolution belongs to fuzzy matching.

**Actor enumerations — extraction:** When the text enumerates actors through explicit designations, extract each as an independent CHAR mention. Preserve their literal spans and omit the initial articles and the conjunction joining them.

**Example:** In “The women cacao producers and the Brazil nut collectors participated in the workshop,” extract separately:

- “women cacao producers” → CHAR.
- “Brazil nut collectors” → CHAR.

In enumerations with omitted words or shared modifiers, preserve only continuous spans identifiable in context, according to the general rule.

## 7. Ambiguity and Unresolvable Cases

Ambiguity exists when the context allows more than one interpretation of the category, referent, or boundaries. Choose the category best supported by the contextual function; omit the expression if none has sufficient evidence. Do not use a generic fallback category or assign labels based on external knowledge.

| `ambiguity` | Criterion |
|---|---|
| `low` | Designation, function, and boundaries are clear in the context received. |
| `medium` | Another plausible reading exists, but the context favors the chosen one. |
| `high` | A relevant doubt persists even though there is evidence for the chosen category. |

These levels indicate the need for review, not calibrated probabilities. `high` does not compensate for a lack of evidence. NER returns only the chosen category and level; alternatives and reasons are recorded separately during pilot review without adding fields to the contract. Review all `high` mentions and `medium` category boundary cases before accepting the document's extraction.

## 8. Input and Output Format

The service segments the clean text and sends chunks of up to three paragraphs, with a target threshold of 12,000 characters. An individual paragraph exceeding that threshold is preserved in full in the current implementation.

The input contains `document_id`, `document_title`, `section_title`, and `sentences`, a list of objects with `sentence_id` and `text`. Titles may be empty; they guide interpretation without creating mentions absent from the sentences. Sentence identifiers are calculated locally from their absolute positions and must be copied without modification.

Input example:

```json
{
  "document_id": "example",
  "document_title": "",
  "section_title": "",
  "sentences": [{"sentence_id": "s-000000000", "text": "The cooperative La Esperanza participates."}]
}
```

Respond through `submit_entity_annotations`, with `document_id` and `annotations`. Each annotation contains exactly four required fields:

| Field | Content |
|---|---|
| `label` | One of the ten exact codes in section 4. |
| `text` | A continuous literal span from an input sentence. |
| `sentence_id` | That sentence's identifier. |
| `ambiguity` | `low`, `medium`, or `high`, according to section 7. |

```json
{
  "document_id": "example",
  "annotations": [{"label": "CHAR", "text": "cooperative La Esperanza", "sentence_id": "s-000000000", "ambiguity": "low"}]
}
```

If there are no valid mentions, return `annotations: []`. Do not add explanations, alternatives, positions, canonical attributes, or relationships.

The code renames `label` to `category`, locates each literal occurrence, and adds `start`, `end` (exclusive), and `context` (source sentence), retaining `sentence_id`, `text`, and `ambiguity`. Positions are Python character indices into the clean text: `texto[start:end] == text`. The NER JSON stores `document_id` and `entities`; it does not yet create canonical nodes.

The service checks the fields, document identifier, labels, sentences, literal wording, ambiguity, and overlaps. If a response loses annotations because of these errors, it asks the model for up to two corrections of the chunk, identifying the conflicting spans. If the errors persist, it fails without saving a partial result; it also fails on truncation or absence of the required tool. Used in isolation, the parser retains its tolerant mode for compatibility, but NER requires a valid response before accepting the chunk. A structurally valid output still requires semantic review.

## 9. Complete Application Examples

The ten demonstrations in `data/ner/few_shot_examples.json` illustrate the ten categories; their provenance is illustrative, and they are not an annotated reference set drawn from the corpus. The category descriptions in section 5 explain the category boundaries.

The following limited cases show all expected annotations; copy the input `sentence_id` in each case:

| Text | Annotations (`label`: `text`, `ambiguity`) |
|---|---|
| The community of San Pedro decided to participate. | CHAR: “community of San Pedro”, `low`; LOC: “San Pedro”, `low`. |
| The workshop took place in the community of San Pedro. | LOC: “San Pedro”, `low`. |
| The municipality did not participate. | CHAR: “municipality”, `low`; negation remains in context. |
| The Asociación de Productores de Cacao (APC) participated. | CHAR: “Asociación de Productores de Cacao”, `low`; CHAR: “APC”, `low`. |
| mining and mining. | Two PRAC annotations: “mining”, `low`, at distinct positions. |
| Thank you for your attention. | `annotations: []`. |

In a factual sentence such as “Flowering occurs in August,” do not add KNOW without identifying knowledge or attributing it. An acronym without a recognizable function does not automatically receive CHAR either. Actual uncertainties from the pilot are reviewed using section 7; do not invent a case of high ambiguity to replace that review.

## 10. Validation and Maintenance

1. Select a real document of manageable length and preserve its complete clean text, identifier, and SHA-256 hash. Run only NER with the current versions; preserve results and warnings for review.
2. Check labels, literal wording, positions, sentences, repetitions, and nesting. Compare the final annotations received with those retained: they must match. Also preserve the previous corrected responses and the number of retries. Review empty chunks.
3. Read all pilot sentences, including those without mentions, to detect omissions, incorrect assignments, and overly broad spans. Pay particular attention to KNOW/ATT/SKILL/PRAC, infrastructure/LOC, proposed rules, acronyms, and `medium` or `high` mentions.
4. Record corrections and their rationale; human review adjudicates the reference set. Separate these development data from a subsequent evaluation using different documents, and keep the demonstrations identified as illustrative. A single document does not validate absent categories or demonstrate quality across all languages.
5. Before processing the corpus, require zero unresolved structural errors and review all disagreements detected in the pilot. Do not claim measured precision or recall without an adjudicated reference set. Once one exists, calculate precision, recall, and F1 using exact matches of position and category, together with errors by category; set the thresholds for expanded evaluation before measuring performance on held-out documents.
6. If a rule changes as a result of the pilot, update the codebook, definitions, prompt, and affected examples, run the regression checks, and repeat only the affected validation. Compare annotations across versions before processing batches. Evaluate LLM repeatability on fixed text; tests with a simulated provider verify the code, not its stability.

Record the codebook version, commit, configured model, and hashes of the text, definitions, prompts, and demonstrations in the pilot artifact. When loading changes into the API, start or restart its process: prompts are cached in memory, and editing their files alone does not guarantee reloading. Validate fuzzy matching and relationships afterward through their own endpoints.

## Appendix A. Instructions for the Language Model

Operational instructions are maintained in the files used by the service:

| Source | Rules incorporated |
|---|---|
| `src/categories.py` | Ten codes and summaries of the category descriptions in section 5. |
| `data/prompts/ner_prompt.md` | Domain, evidence, context, span boundaries, nesting, repetitions, ambiguity, and output from sections 1–8. |
| `data/prompts/ner_user_prompt.md` | Demonstrations and target sentences; extraction limited to `target_input`. |
| `data/ner/few_shot_examples.json` | Ten illustrative category demonstrations. |
| `src/services/ner.py` | Four-field schema, segmentation, literal span location, and contract checks. |

The service inserts the definitions into `$category_definitions` and assembles the user prompt with examples and input. It does not send this entire codebook or instructions for canonicalization or relationship construction to the model.
