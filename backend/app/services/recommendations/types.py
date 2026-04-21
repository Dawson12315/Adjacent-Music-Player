from dataclasses import dataclass, field


@dataclass
class RetrievedCandidate:
    track_id: int
    source_scores: dict[str, float] = field(default_factory=dict)

    def add_score(self, source_name: str, score: float) -> None:
        self.source_scores[source_name] = (
            self.source_scores.get(source_name, 0.0) + score
        )

    @property
    def total_retrieval_score(self) -> float:
        return sum(self.source_scores.values())