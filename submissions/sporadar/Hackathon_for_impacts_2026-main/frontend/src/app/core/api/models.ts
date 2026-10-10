// Alias lisibles des types GÉNÉRÉS depuis openapi.proposed.yaml (pnpm gen:api).
// Aucun type réglementaire n'est écrit à la main : si le contrat change, on régénère schema.d.ts.
import type { components } from './schema';

type Schemas = components['schemas'];

export type Answer = Schemas['Answer'];
export type AskRequest = Schemas['AskRequest'];
export type AskParameters = Schemas['AskParameters'];
export type AuthorizedUse = Schemas['AuthorizedUse'];
export type ComparisonCell = Schemas['ComparisonCell'];
export type ComparisonResponse = Schemas['ComparisonResponse'];
export type ComparisonRow = Schemas['ComparisonRow'];
export type CountryCoverage = Schemas['CountryCoverage'];
export type DataIssue = Schemas['DataIssue'];
export type Evidence = Schemas['Evidence'];
export type ExpirationItem = Schemas['ExpirationItem'];
export type ExpirationsResponse = Schemas['ExpirationsResponse'];
export type Fact = Schemas['Fact'];
export type IssuesResponse = Schemas['IssuesResponse'];
export type Product = Schemas['Product'];
export type ProductMatch = Schemas['ProductMatch'];
export type Registration = Schemas['Registration'];
export type Review = Schemas['Review'];
export type ReviewRequest = Schemas['ReviewRequest'];
export type SisterCandidate = Schemas['SisterCandidate'];
export type SisterCandidatesResponse = Schemas['SisterCandidatesResponse'];
export type SourceInfo = Schemas['SourceInfo'];
export type SuggestedQuestion = Schemas['SuggestedQuestion'];

export type AnswerStatus = Schemas['AnswerStatus'];
export type CellState = Schemas['CellState'];
export type CoverageOutcome = Schemas['CoverageOutcome'];
export type Intent = Schemas['Intent'];
export type IssueType = Schemas['IssueType'];
export type MappingStatus = Schemas['MappingStatus'];
export type RegistrationStatus = Schemas['RegistrationStatus'];
export type ReviewStatus = Schemas['ReviewStatus'];
export type ValidationStatus = Schemas['ValidationStatus'];
