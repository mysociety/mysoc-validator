from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return str(self.value)


class TranscriptType(StrEnum):
    DEBATES = "debates"
    WRITTEN_QUESTIONS = "written_questions"
    WRITTEN_STATEMENTS = "written_statements"


class Chamber(StrEnum):
    COMMONS = "house-of-commons"
    LORDS = "house-of-lords"
    SCOTLAND = "scottish-parliament"
    SENEDD = "welsh-parliament"
    LONDON = "london-assembly"
    NORTHERN_IRELAND = "northern-ireland-assembly"


class IdentifierScheme(StrEnum):
    DATADOTPARL = "datadotparl_id"
    MNIS = "datadotparl_id"
    PIMS = "pims_id"
    HISTORIC_HANSARD = "historichansard_id"
    PEERAGE_TYPE = "peeragetype"
    WIKIDATA = "wikidata"
    SCOTPARL = "scotparl_id"
    SENEDD = "senedd"
    NI_ASSEMBLY = "data.niassembly.gov.uk"
