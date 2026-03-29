class EvidenceEvaluator:

    @staticmethod
    def evaluate(*, dao_results, structured_plan, entity: str):
        entities = dao_results.get(entity, []) or []
        entity_count = len(entities)

        # -----------------------------
        # Structural signals
        # -----------------------------
        post_aggs = bool(structured_plan.get("post_aggregations"))
        global_aggs = bool(structured_plan.get("global_aggregations"))
        post_filters = bool(structured_plan.get("post_filters"))

        formulas = any(
            agg.get("aggregate") == "FORMULA"
            for agg in structured_plan.get("post_aggregations", [])
        )

        # -----------------------------
        # Evidence density
        # -----------------------------
        expanded_fields = [
            a["attr"] for a in structured_plan.get("attributes", [])
            if a["attr"] != "core"
        ]

        evidence_density = "low"
        if expanded_fields and entity_count > 0:
            avg_rows = sum(
                len(e.get(expanded_fields[0], []) or [])
                for e in entities
            ) / entity_count
            if avg_rows >= 5:
                evidence_density = "high"
            elif avg_rows >= 2:
                evidence_density = "medium"

        # -----------------------------
        # Assumption detection
        # -----------------------------
        assumptions = []

        plan_text = str(structured_plan).lower()
        if "absence" in plan_text or "missing" in plan_text:
            assumptions.append("Implicit missing-data interpretation")

        if formulas and post_filters:
            assumptions.append("Derived-metric filtering assumption")

        # -----------------------------
        # Stability assessment
        # -----------------------------
        stability = "high"
        if formulas:
            stability = "medium"
        if formulas and entity_count <= 2:
            stability = "low"

        # -----------------------------
        # Confidence synthesis
        # -----------------------------
        confidence = "high"

        if entity_count == 0:
            confidence = "low"
        elif entity_count == 1 and evidence_density == "low":
            confidence = "medium"

        if assumptions:
            confidence = "medium"

        if stability == "low":
            confidence = "low"

        # -----------------------------
        # Export gate (STRICT)
        # -----------------------------
        export_worthy = (
            confidence == "high"
            and evidence_density != "low"
            and not assumptions
        )

        return {
            "entity": entity,
            "entity_count": entity_count,
            "evidence_density": evidence_density,
            "post_aggregations_used": post_aggs,
            "global_aggregations_used": global_aggs,
            "formulas_used": formulas,
            "post_filters_used": post_filters,
            "assumptions_detected": assumptions,
            "stability_level": stability,
            "confidence_level": confidence,
            "export_worthy": export_worthy
        }
