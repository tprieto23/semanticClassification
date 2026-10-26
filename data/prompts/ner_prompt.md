# Semantic entity extraction

Use the following codebook as the complete specification for annotation. Your task is to extract literal words or short spans from the supplied target sentences and classify them into its ten categories. Operational and maintenance notes describe the service workflow; perform only extraction and classification for the current input.

Apply the codebook to every sentence in `target_input.sentences`. Extract only literal spans from those sentences, preserving their original language, and record each valid occurrence. Copy `document_id` and the corresponding `sentence_id` exactly. Return the complete annotations through `submit_entity_annotations`, with only `label`, `text`, `sentence_id`, and `ambiguity` for each annotation. If no mentions qualify, return an empty `annotations` array.

<codebook>
$codebook
</codebook>

<target_input>$json_input</target_input>
