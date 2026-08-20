from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from .metrics import RECOMMENDATION_ROLES
from .models import ObservationSet


def import_observation_set_sqlite(
    observation_set: ObservationSet,
    db_path: str | Path,
) -> dict[str, int | str]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _ensure_schema(connection)
        _replace_observation_set(connection, observation_set)

    return {
        "db_path": str(path),
        "run_id": observation_set.id,
        "observations": len(observation_set.observations),
        "citations": sum(len(observation.citations) for observation in observation_set.observations),
        "retrieved_sources": sum(
            len(observation.retrieved_sources)
            for observation in observation_set.observations
        ),
        "product_mentions": sum(len(observation.mentions) for observation in observation_set.observations),
    }


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            started_at TEXT,
            completed_at TEXT,
            prompt_file TEXT,
            product_file TEXT,
            repetitions INTEGER,
            providers TEXT,
            config_json TEXT
        );

        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            prompt_id TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            surface TEXT,
            repetition INTEGER,
            timestamp TEXT,
            language TEXT,
            region TEXT,
            answer_text TEXT NOT NULL,
            raw_request_json TEXT NOT NULL,
            raw_response_json TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS citations (
            id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL,
            url TEXT NOT NULL,
            domain TEXT,
            title TEXT,
            FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS retrieved_sources (
            id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL,
            url TEXT NOT NULL,
            domain TEXT,
            title TEXT,
            rank INTEGER,
            FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS product_mentions (
            id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL,
            product_id TEXT,
            display_name TEXT,
            mentioned INTEGER NOT NULL,
            recommended INTEGER NOT NULL,
            recommendation_position INTEGER,
            stance TEXT,
            claims_json TEXT NOT NULL,
            FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_observations_run_id ON observations(run_id);
        CREATE INDEX IF NOT EXISTS idx_observations_prompt_id ON observations(prompt_id);
        CREATE INDEX IF NOT EXISTS idx_observations_provider ON observations(provider);
        CREATE INDEX IF NOT EXISTS idx_citations_observation_id ON citations(observation_id);
        CREATE INDEX IF NOT EXISTS idx_retrieved_sources_observation_id ON retrieved_sources(observation_id);
        CREATE INDEX IF NOT EXISTS idx_product_mentions_observation_id ON product_mentions(observation_id);
        CREATE INDEX IF NOT EXISTS idx_product_mentions_product_id ON product_mentions(product_id);
        """
    )


def _replace_observation_set(
    connection: sqlite3.Connection,
    observation_set: ObservationSet,
) -> None:
    connection.execute("DELETE FROM runs WHERE id = ?", (observation_set.id,))
    connection.execute(
        """
        INSERT INTO runs (
            id,
            started_at,
            completed_at,
            prompt_file,
            product_file,
            repetitions,
            providers,
            config_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observation_set.id,
            _first_timestamp(observation_set),
            _last_timestamp(observation_set),
            observation_set.attributes.get("prompt_file"),
            observation_set.attributes.get("product_file"),
            _max_repetition(observation_set),
            json.dumps(_providers(observation_set)),
            json.dumps(asdict(observation_set), sort_keys=True),
        ),
    )
    for observation in observation_set.observations:
        connection.execute(
            """
            INSERT INTO observations (
                id,
                run_id,
                prompt_id,
                provider,
                model,
                surface,
                repetition,
                timestamp,
                language,
                region,
                answer_text,
                raw_request_json,
                raw_response_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.id,
                observation_set.id,
                observation.prompt_id,
                observation.provider,
                observation.model,
                observation.surface,
                observation.repetition,
                observation.timestamp,
                observation.language,
                observation.region,
                observation.raw_answer,
                json.dumps(observation.raw_request, sort_keys=True),
                json.dumps(observation.raw_response, sort_keys=True),
            ),
        )
        for index, citation in enumerate(observation.citations, start=1):
            connection.execute(
                """
                INSERT INTO citations (id, observation_id, url, domain, title)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"{observation.id}:citation:{index}",
                    observation.id,
                    citation.url,
                    citation.domain or _domain(citation.url),
                    citation.title,
                ),
            )
        for index, source in enumerate(observation.retrieved_sources, start=1):
            connection.execute(
                """
                INSERT INTO retrieved_sources (id, observation_id, url, domain, title, rank)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{observation.id}:retrieved:{index}",
                    observation.id,
                    source.url,
                    source.domain or _domain(source.url),
                    source.title,
                    source.rank,
                ),
            )
        for index, mention in enumerate(observation.mentions, start=1):
            connection.execute(
                """
                INSERT INTO product_mentions (
                    id,
                    observation_id,
                    product_id,
                    display_name,
                    mentioned,
                    recommended,
                    recommendation_position,
                    stance,
                    claims_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{observation.id}:mention:{index}",
                    observation.id,
                    mention.product_id,
                    mention.display_name or mention.entity,
                    1,
                    1 if mention.role in RECOMMENDATION_ROLES else 0,
                    mention.rank,
                    mention.stance,
                    json.dumps(tuple(mention.claims), sort_keys=True),
                ),
            )


def _first_timestamp(observation_set: ObservationSet) -> str | None:
    timestamps = sorted(
        observation.timestamp
        for observation in observation_set.observations
        if observation.timestamp
    )
    return timestamps[0] if timestamps else None


def _last_timestamp(observation_set: ObservationSet) -> str | None:
    timestamps = sorted(
        observation.timestamp
        for observation in observation_set.observations
        if observation.timestamp
    )
    return timestamps[-1] if timestamps else None


def _max_repetition(observation_set: ObservationSet) -> int | None:
    repetitions = [
        observation.repetition
        for observation in observation_set.observations
        if observation.repetition is not None
    ]
    return max(repetitions) if repetitions else None


def _providers(observation_set: ObservationSet) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                observation.provider or observation.engine
                for observation in observation_set.observations
                if observation.provider or observation.engine
            }
        )
    )


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()
