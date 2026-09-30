'''Build sourced, AI-authored R2/R4/R6 candidates for human review.'''

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Mapping, Sequence

from .authoring import PROTOCOL_VERSION, load_authored
from .io import sha256_file, write_jsonl


NIST_PUBLIC = 'NIST U.S. Government work; factual citation only'
NASA_PUBLIC = 'NASA U.S. Government work; factual citation only'
WIKIDATA_CC0 = 'CC0-1.0'
GOV_FACT = 'Official government source; factual citation only'


def _base(
    *,
    example_id: str,
    family_id: str,
    dimension: str,
    level: str,
    question: str,
    answers: Sequence[str],
    interpretations: Mapping[str, Sequence[str]],
    domain: str,
    source_urls: Sequence[str],
    source_licenses: Sequence[str],
    entity_ids: Sequence[str],
    fact_ids: Sequence[str],
    template_id: str,
    prerequisite: str,
    rationale: str,
    answer_type: str = 'categorical',
    granularity: str = 'exact accepted answer',
    tolerance: float | None = None,
) -> dict[str, object]:
    return {
        'protocol_version': PROTOCOL_VERSION,
        'example_id': example_id,
        'family_id': family_id,
        'dimension': dimension,
        'question': question,
        'accepted_answers': list(answers),
        'interpretation_answers': {key: list(values) for key, values in interpretations.items()},
        'adjudicated_level': level,
        'adjudication_status': 'draft',
        'independent_labels': {},
        'adjudicator_id': '',
        'author_id': 'codex_candidate_generator_v1',
        'contributor_consent': False,
        'domain_name': domain,
        'expertise_prerequisite': prerequisite,
        'expertise_rationale': rationale,
        'precision_answer_type': answer_type,
        'required_granularity': granularity,
        'numeric_tolerance': tolerance,
        'entity_id': list(entity_ids),
        'template_id': template_id,
        'source_fact_id': list(fact_ids),
        'source_urls': list(source_urls),
        'source_licenses': list(source_licenses),
    }


def _r2_family(
    family: str,
    prompts: Sequence[str],
    answers: Sequence[Sequence[str]],
    granularities: Sequence[str],
    tolerances: Sequence[float | None],
    *,
    source_url: str,
    license_label: str,
    answer_type: str,
    entity: str,
    fact: str,
) -> list[dict[str, object]]:
    levels = ('coarse', 'medium', 'fine')
    return [
        _base(
            example_id=f'r2:{family}:{level}',
            family_id=f'r2:{family}',
            dimension='R2',
            level=level,
            question=prompt,
            answers=answer,
            interpretations={'intended_reading': answer},
            domain='general_science',
            source_urls=(source_url,),
            source_licenses=(license_label,),
            entity_ids=(entity,),
            fact_ids=(fact,),
            template_id=f'r2:precision:{family}',
            prerequisite='General scientific literacy',
            rationale='R6 is held at a general-science control while requested answer precision varies.',
            answer_type=answer_type,
            granularity=granularity,
            tolerance=tolerance,
        )
        for level, prompt, answer, granularity, tolerance in zip(
            levels, prompts, answers, granularities, tolerances, strict=True
        )
    ]


def r2_candidates() -> list[dict[str, object]]:
    nist = 'https://www.nist.gov/pml/special-publication-330/sp-330-section-2'
    rows: list[dict[str, object]] = []
    rows += _r2_family(
        'speed_of_light',
        (
            'Approximately how many kilometres per second does light travel in vacuum?',
            'To the nearest kilometre per second, what is the speed of light in vacuum?',
            'What is the exact defined speed of light in vacuum in metres per second?',
        ),
        (('about 300,000 km/s', '300,000 km/s'), ('299,792 km/s',), ('299,792,458 m/s',)),
        ('nearest 1000 km/s', 'nearest 1 km/s', 'exact SI-defined integer in m/s'),
        (1000.0, 0.5, 0.0),
        source_url=nist,
        license_label=NIST_PUBLIC,
        answer_type='numeric',
        entity='constant:speed_of_light',
        fact='nist:si:c',
    )
    rows += _r2_family(
        'avogadro_constant',
        (
            'Approximately what is the Avogadro constant in reciprocal moles?',
            'Give the Avogadro constant to four significant digits in reciprocal moles.',
            'What is the exact defined Avogadro constant in reciprocal moles?',
        ),
        (('about 6 × 10^23 mol^-1',), ('6.022 × 10^23 mol^-1',), ('6.02214076 × 10^23 mol^-1',)),
        ('one significant digit', 'four significant digits', 'exact SI-defined digits'),
        (5e22, 5e19, 0.0),
        source_url=nist,
        license_label=NIST_PUBLIC,
        answer_type='numeric',
        entity='constant:avogadro',
        fact='nist:si:avogadro',
    )
    rows += _r2_family(
        'planck_constant',
        (
            'Approximately what is the Planck constant in joule-seconds?',
            'Give the Planck constant to four significant digits in joule-seconds.',
            'What is the exact defined Planck constant in joule-seconds?',
        ),
        (('about 6.6 × 10^-34 J s',), ('6.626 × 10^-34 J s',), ('6.62607015 × 10^-34 J s',)),
        ('two significant digits', 'four significant digits', 'exact SI-defined digits'),
        (5e-36, 5e-38, 0.0),
        source_url=nist,
        license_label=NIST_PUBLIC,
        answer_type='numeric',
        entity='constant:planck',
        fact='nist:si:planck',
    )
    rows += _r2_family(
        'apollo11_landing',
        (
            'In what year did Apollo 11 land on the Moon?',
            'In what month and year did Apollo 11 land on the Moon?',
            'On what calendar date did Apollo 11 land on the Moon?',
        ),
        (('1969',), ('July 1969',), ('1969-07-20', '20 July 1969', 'July 20, 1969')),
        ('calendar year', 'calendar month', 'ISO calendar day'),
        (None, None, None),
        source_url='https://www.nasa.gov/mission/apollo-11/',
        license_label=NASA_PUBLIC,
        answer_type='date',
        entity='mission:apollo_11',
        fact='nasa:apollo11:lunar_landing_date',
    )
    return rows


def _r4_family(
    family: str,
    controls: Sequence[tuple[str, str, str, str]],
    ambiguous_question: str,
    *,
    sources: Sequence[str],
    licenses: Sequence[str],
    template: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    interpretations: dict[str, Sequence[str]] = {}
    entities: list[str] = []
    facts: list[str] = []
    for key, control_question, answer, entity in controls:
        fact = f'fact:{family}:{key}'
        interpretations[key] = (answer,)
        entities.append(entity)
        facts.append(fact)
        rows.append(
            _base(
                example_id=f'r4:{family}:control:{key}',
                family_id=f'r4:{family}',
                dimension='R4',
                level='unambiguous',
                question=control_question,
                answers=(answer,),
                interpretations={key: (answer,)},
                domain='general_knowledge',
                source_urls=sources,
                source_licenses=licenses,
                entity_ids=(entity,),
                fact_ids=(fact,),
                template_id=template,
                prerequisite='No specialist training required',
                rationale='R6 is held at the general-knowledge control while wording ambiguity varies.',
            )
        )
    answers = tuple(value for values in interpretations.values() for value in values)
    level = 'two_way' if len(interpretations) == 2 else 'three_plus'
    rows.append(
        _base(
            example_id=f'r4:{family}:ambiguous',
            family_id=f'r4:{family}',
            dimension='R4',
            level=level,
            question=ambiguous_question,
            answers=answers,
            interpretations=interpretations,
            domain='general_knowledge',
            source_urls=sources,
            source_licenses=licenses,
            entity_ids=entities,
            fact_ids=facts,
            template_id=template,
            prerequisite='No specialist training required',
            rationale='R6 is held at the general-knowledge control while wording ambiguity varies.',
        )
    )
    return rows


def r4_candidates() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    rows += _r4_family(
        'georgia_capital',
        (
            ('country', 'What is the capital of the country Georgia?', 'Tbilisi', 'wikidata:Q230'),
            ('us_state', 'What is the capital of the U.S. state of Georgia?', 'Atlanta', 'wikidata:Q1428'),
        ),
        'What is the capital of Georgia?',
        sources=('https://www.wikidata.org/wiki/Q230', 'https://www.wikidata.org/wiki/Q1428'),
        licenses=(WIKIDATA_CC0, WIKIDATA_CC0),
        template='r4:shared_place_name:capital',
    )
    rows += _r4_family(
        'congo_capital',
        (
            ('democratic_republic', 'What is the capital of the Democratic Republic of the Congo?', 'Kinshasa', 'wikidata:Q974'),
            ('republic', 'What is the capital of the Republic of the Congo?', 'Brazzaville', 'wikidata:Q971'),
        ),
        'What is the capital of the Congo?',
        sources=('https://www.wikidata.org/wiki/Q974', 'https://www.wikidata.org/wiki/Q971'),
        licenses=(WIKIDATA_CC0, WIKIDATA_CC0),
        template='r4:shared_place_name:capital',
    )
    rows += _r4_family(
        'korea_capital',
        (
            ('south', 'What is the capital of South Korea?', 'Seoul', 'wikidata:Q884'),
            ('north', 'What is the capital of North Korea?', 'Pyongyang', 'wikidata:Q423'),
        ),
        'What is the capital of Korea?',
        sources=('https://www.wikidata.org/wiki/Q884', 'https://www.wikidata.org/wiki/Q423'),
        licenses=(WIKIDATA_CC0, WIKIDATA_CC0),
        template='r4:underspecified_partition:capital',
    )
    rows += _r4_family(
        'cambridge_river',
        (
            ('england', 'Which river runs through Cambridge, England?', 'River Cam', 'wikidata:Q350'),
            ('massachusetts', 'Which river borders Cambridge, Massachusetts?', 'Charles River', 'wikidata:Q49111'),
        ),
        'Which river runs through Cambridge?',
        sources=('https://www.wikidata.org/wiki/Q944772', 'https://www.wikidata.org/wiki/Q794927'),
        licenses=(WIKIDATA_CC0, WIKIDATA_CC0),
        template='r4:shared_place_name:river',
    )
    rows += _r4_family(
        'columbus_state',
        (
            ('ohio', 'In which state is Columbus, the capital city of Ohio?', 'Ohio', 'city:columbus_ohio'),
            ('georgia', 'In which state is Columbus on the Chattahoochee River?', 'Georgia', 'city:columbus_georgia'),
            ('indiana', 'In which state is Columbus, the seat of Bartholomew County?', 'Indiana', 'city:columbus_indiana'),
        ),
        'Among Ohio, Georgia, and Indiana, which state contains a city named Columbus?',
        sources=('https://www.columbus.gov/', 'https://www.columbusga.gov/', 'https://www.columbus.in.gov/'),
        licenses=(GOV_FACT, GOV_FACT, GOV_FACT),
        template='r4:declared_universe:shared_city_name',
    )
    return rows


def r6_candidates() -> list[dict[str, object]]:
    definitions = (
        ('computer_science', 'general', 'How many distinct values can one binary digit represent?', ('2', 'two'), 'Basic digital literacy', 'A binary digit is ordinary introductory computing knowledge.', 'https://csrc.nist.gov/glossary/term/bit', NIST_PUBLIC, 'cs:bit'),
        ('computer_science', 'specialized', 'What is the standard worst-case time complexity of merge sort?', ('O(n log n)', 'Theta(n log n)', 'Θ(n log n)'), 'Undergraduate algorithms', 'Asymptotic worst-case analysis is normally learned in formal computer-science study.', 'https://xlinux.nist.gov/dads/HTML/mergeSort.html', NIST_PUBLIC, 'cs:merge_sort'),
        ('computer_science', 'expert', 'Which hash-function property requires it to be computationally infeasible to find two distinct inputs with the same output?', ('collision resistance',), 'Graduate cryptography or security engineering', 'Distinguishing formal cryptographic security properties requires specialist training.', 'https://csrc.nist.gov/glossary/term/collision_resistance', NIST_PUBLIC, 'cs:collision_resistance'),
        ('physics', 'general', 'What is the SI unit of force?', ('newton', 'N'), 'General school science', 'The named SI unit of force is standard general science knowledge.', 'https://www.nist.gov/pml/owm/si-units-force', NIST_PUBLIC, 'physics:newton'),
        ('physics', 'specialized', 'Which equation relates a photon energy E to its frequency nu using the Planck constant?', ('E = hν', 'E=hν', 'E = h nu'), 'Undergraduate modern physics', 'The photon energy-frequency relation is normally taught in university physics.', 'https://www.nist.gov/pml/special-publication-330/sp-330-section-2', NIST_PUBLIC, 'physics:photon_energy'),
        ('physics', 'expert', 'Which dimensionless constant measures the strength of the electromagnetic interaction between charged particles and photons?', ('fine-structure constant', 'alpha', 'α'), 'Advanced quantum physics', 'Identifying coupling constants by physical role requires advanced subject knowledge.', 'https://physics.nist.gov/cuu/Constants/alpha.html', NIST_PUBLIC, 'physics:fine_structure'),
        ('astronomy', 'general', 'What is the largest planet in the Solar System?', ('Jupiter',), 'General astronomy knowledge', 'The relative size of the planets is common general knowledge.', 'https://www.jpl.nasa.gov/missions/juno/', NASA_PUBLIC, 'astronomy:jupiter'),
        ('astronomy', 'specialized', 'What is the boundary around a black hole beyond which even light cannot escape?', ('event horizon',), 'Introductory university astronomy', 'Black-hole structure terminology is normally learned in astronomy or physics study.', 'https://www.nasa.gov/universe/what-are-black-holes/', NASA_PUBLIC, 'astronomy:event_horizon'),
        ('astronomy', 'expert', 'What name is given to the radius at which a non-rotating black hole has its event horizon?', ('Schwarzschild radius',), 'Relativity or advanced astrophysics', 'Connecting a non-rotating black-hole horizon to its formal radius requires advanced training.', 'https://imagine.gsfc.nasa.gov/science/objects/black_holes1.html', NASA_PUBLIC, 'astronomy:schwarzschild_radius'),
    )
    return [
        _base(
            example_id=f'r6:{domain}:{level}',
            family_id=f'r6:{domain}',
            dimension='R6',
            level=level,
            question=question,
            answers=answers,
            interpretations={'intended_reading': answers},
            domain=domain,
            source_urls=(url,),
            source_licenses=(license_label,),
            entity_ids=(fact,),
            fact_ids=(fact,),
            template_id=f'r6:{domain}:knowledge_requirement',
            prerequisite=prerequisite,
            rationale=rationale,
        )
        for domain, level, question, answers, prerequisite, rationale, url, license_label, fact in definitions
    ]


def build_candidates() -> list[dict[str, object]]:
    return r2_candidates() + r4_candidates() + r6_candidates()


def write_candidates(output: str | Path) -> Path:
    target = Path(output)
    rows = build_candidates()
    write_jsonl(target, rows)
    valid, errors = load_authored(target)
    if errors or len(valid) != len(rows):
        raise ValueError(f'generated candidate validation failed: {errors}')
    counts = Counter(str(row['dimension']) for row in valid)
    level_counts = {
        dimension: dict(
            Counter(str(row['adjudicated_level']) for row in valid if row['dimension'] == dimension)
        )
        for dimension in ('R2', 'R4', 'R6')
    }
    card = target.with_name('CANDIDATE_CARD.md')
    card.write_text(
        f'''# CalibRead AI-authored candidate pack

- Protocol: `{PROTOCOL_VERSION}`
- Records: {len(valid)}
- Dimension counts: {dict(counts)}
- Candidate level counts: {level_counts}
- Candidate SHA-256: `{sha256_file(target)}`
- Status: draft candidates; zero human-approved gold records
- Author: `codex_candidate_generator_v1`

Questions use original wording and cite factual sources. Source licenses describe
the factual reference; no source question wording was copied. Before acceptance,
each row requires two independent labels, a separate adjudicator, contributor
consent, answer verification, and review of whether its intended level is natural.
''',
        encoding='utf-8',
        newline='\n',
    )
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build sourced R2/R4/R6 review candidates')
    parser.add_argument('--output', type=Path, default=Path('data/candidates/R2_R4_R6_AI_CANDIDATES.jsonl'))
    args = parser.parse_args(argv)
    output = write_candidates(args.output)
    print(json.dumps({'output': str(output), 'records': len(build_candidates()), 'sha256': sha256_file(output)}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
