import Foundation

/// `GET /map` — what Icarus has INDEXED for the connected repo.
///
/// Every field is named `indexed*` for the same reason the brain names them
/// that way (`demo/repo_map.py`): a map built from the corpus describes what
/// Icarus READ, never what EXISTS in the repository. There is deliberately no
/// total-file count and no excluded-file count here, because the brain does not
/// know them and inventing them would be the same failure as a bluffed
/// citation. `exclusionRules` are the rules that were APPLIED, not observations
/// about particular files.
public struct RepoMap: Decodable, Sendable {
    public let repo: String?
    public let commit: String?
    public let indexedFileCount: Int
    /// Distinct FILES per language (never chunks — a file can produce many).
    public let indexedLanguages: [String: Int]
    /// Distinct files per top-level directory ("." for repo-root files).
    public let indexedDirectories: [String: Int]
    public let indexedDocumentation: IndexedDocumentation
    public let indexedEntryPoints: [EntryPoint]
    /// Committed test data, counted WITHIN the totals above and named
    /// separately. Optional so a brain deployed before this field existed
    /// still decodes — absent simply means the share is unknown, never zero.
    public let indexedAuxiliary: IndexedAuxiliary?
    public let indexedChunksBySource: [String: Int]
    public let lexicalSearchReady: Bool
    public let semanticIndexingInProgress: Bool
    public let corpusTruncated: Bool
    public let exclusionRules: [String]
    public let limitations: [String]
    /// How the code is ARRANGED, derived from its own imports
    /// (`demo/structure.py`). Optional so a brain deployed before this field
    /// existed still decodes -- absent means Icarus did not report an
    /// arrangement, never that the repository has none.
    public let indexedStructure: IndexedStructure?

    enum CodingKeys: String, CodingKey {
        case repo, commit, limitations
        case indexedStructure = "indexed_structure"
        case indexedFileCount = "indexed_file_count"
        case indexedLanguages = "indexed_languages"
        case indexedDirectories = "indexed_directories"
        case indexedDocumentation = "indexed_documentation"
        case indexedEntryPoints = "indexed_entry_points"
        case indexedAuxiliary = "indexed_auxiliary"
        case indexedChunksBySource = "indexed_chunks_by_source"
        case lexicalSearchReady = "lexical_search_ready"
        case semanticIndexingInProgress = "semantic_indexing_in_progress"
        case corpusTruncated = "corpus_truncated"
        case exclusionRules = "exclusion_rules"
    }

    public init(repo: String?, commit: String?, indexedFileCount: Int,
                indexedLanguages: [String: Int], indexedDirectories: [String: Int],
                indexedDocumentation: IndexedDocumentation,
                indexedEntryPoints: [EntryPoint], indexedAuxiliary: IndexedAuxiliary? = nil,
                indexedChunksBySource: [String: Int],
                lexicalSearchReady: Bool, semanticIndexingInProgress: Bool,
                corpusTruncated: Bool, exclusionRules: [String], limitations: [String],
                indexedStructure: IndexedStructure? = nil) {
        self.indexedStructure = indexedStructure
        self.repo = repo
        self.commit = commit
        self.indexedFileCount = indexedFileCount
        self.indexedLanguages = indexedLanguages
        self.indexedDirectories = indexedDirectories
        self.indexedDocumentation = indexedDocumentation
        self.indexedEntryPoints = indexedEntryPoints
        self.indexedAuxiliary = indexedAuxiliary
        self.indexedChunksBySource = indexedChunksBySource
        self.lexicalSearchReady = lexicalSearchReady
        self.semanticIndexingInProgress = semanticIndexingInProgress
        self.corpusTruncated = corpusTruncated
        self.exclusionRules = exclusionRules
        self.limitations = limitations
    }
}

/// How much of what Icarus read is supporting material rather than the project.
///
/// A large committed fixture tree makes a repository look like something it is
/// not — measured on this repo, 348 of 500 indexed files sat under
/// `evals/fixtures/`, so the language mix read as a mobile codebase. The count
/// sits BESIDE the totals rather than being subtracted from them, because the
/// map's one contract is that it describes what Icarus READ.
public struct IndexedAuxiliary: Decodable, Sendable {
    public let fileCount: Int
    /// The rule that produced the count, in words — never an opaque number.
    public let rule: String

    enum CodingKeys: String, CodingKey {
        case rule
        case fileCount = "file_count"
    }

    public init(fileCount: Int, rule: String) {
        self.fileCount = fileCount
        self.rule = rule
    }
}

public struct IndexedDocumentation: Decodable, Sendable {
    public let files: [String]
    /// nil when NO readme was indexed. Rendered as an explicit "none was
    /// indexed", never as silence — the absence is a fact about the corpus.
    public let readme: String?

    public init(files: [String], readme: String?) {
        self.files = files
        self.readme = readme
    }
}

/// One file the brain believes is a place to start reading, with the RULE that
/// produced it. Nothing here is scored or ranked: a rule fired, or it didn't.
public struct EntryPoint: Decodable, Identifiable, Sendable {
    public let path: String
    public let rules: [EntryPointRule]
    public var id: String { path }

    public init(path: String, rules: [EntryPointRule]) {
        self.path = path
        self.rules = rules
    }
}

public struct EntryPointRule: Decodable, Identifiable, Sendable {
    public let rule: String
    /// The indexed chunk that proves it — citable like any other evidence.
    public let evidenceRef: String?
    public let detail: String

    public var id: String { rule }

    enum CodingKeys: String, CodingKey {
        case rule, detail
        case evidenceRef = "evidence_ref"
    }

    public init(rule: String, evidenceRef: String?, detail: String) {
        self.rule = rule
        self.evidenceRef = evidenceRef
        self.detail = detail
    }
}

public extension RepoMap {
    /// Languages biggest-first, for display. Ties break on name so the order is
    /// stable between renders rather than dictionary-order roulette.
    var languagesByFileCount: [(name: String, files: Int)] {
        indexedLanguages.sorted { ($0.value, $1.key) > ($1.value, $0.key) }
            .map { (name: $0.key, files: $0.value) }
    }

    var directoriesByFileCount: [(name: String, files: Int)] {
        indexedDirectories.sorted { ($0.value, $1.key) > ($1.value, $0.key) }
            .map { (name: $0.key, files: $0.value) }
    }
}

/// How the code is ARRANGED, read off its own import statements
/// (`demo/structure.py`).
///
/// This answers the question measurement found hardest — the writer-backed
/// `architecture` step scored 2 of 10 real repositories, and anchoring it to a
/// README provably could not fix it, because a README says what a project is
/// FOR, not how its code is laid out. So it is derived rather than asked, and
/// it cannot bluff: every edge carries the indexed chunk that proves it.
///
/// **An empty arrangement is not a claim that there is none.** Only Python,
/// JavaScript/TypeScript and Go imports are analysed; anything else is listed
/// in `unanalysedLanguages`, and a view MUST say so rather than showing an
/// empty panel that reads as "this project has no structure".
public struct IndexedStructure: Decodable, Equatable, Sendable {
    public let components: [Component]
    public let mostDependedOnFiles: [CoreFile]
    /// Imports seen and not resolved to another indexed file. Mostly
    /// third-party and standard-library imports, which are external by
    /// definition — a large number here is normal and does not mean anything
    /// is missing.
    public let unresolvedImportCount: Int
    /// Indexed languages with no resolver at all. Naming them is what stops an
    /// empty result reading as "no structure exists".
    public let unanalysedLanguages: [String]
    public let limitations: [String]

    private enum CodingKeys: String, CodingKey {
        case components, limitations
        case mostDependedOnFiles = "most_depended_on_files"
        case unresolvedImportCount = "unresolved_import_count"
        case unanalysedLanguages = "unanalysed_languages"
    }

    public struct Component: Decodable, Equatable, Sendable {
        public let path: String
        public let fileCount: Int
        public let dependsOn: [String]
        public let dependedOnBy: [String]
        /// The indexed chunks proving this component's edges — citable like
        /// any other claim Icarus makes.
        public let evidenceRefs: [String]

        private enum CodingKeys: String, CodingKey {
            case path
            case fileCount = "file_count"
            case dependsOn = "depends_on"
            case dependedOnBy = "depended_on_by"
            case evidenceRefs = "evidence_refs"
        }

        public init(path: String, fileCount: Int, dependsOn: [String],
                    dependedOnBy: [String], evidenceRefs: [String]) {
            self.path = path
            self.fileCount = fileCount
            self.dependsOn = dependsOn
            self.dependedOnBy = dependedOnBy
            self.evidenceRefs = evidenceRefs
        }
    }

    public struct CoreFile: Decodable, Equatable, Sendable {
        public let path: String
        public let dependedOnByCount: Int
        public let evidenceRef: String

        private enum CodingKeys: String, CodingKey {
            case path
            case dependedOnByCount = "depended_on_by_count"
            case evidenceRef = "evidence_ref"
        }

        public init(path: String, dependedOnByCount: Int, evidenceRef: String) {
            self.path = path
            self.dependedOnByCount = dependedOnByCount
            self.evidenceRef = evidenceRef
        }
    }

    public init(components: [Component], mostDependedOnFiles: [CoreFile],
                unresolvedImportCount: Int, unanalysedLanguages: [String],
                limitations: [String]) {
        self.components = components
        self.mostDependedOnFiles = mostDependedOnFiles
        self.unresolvedImportCount = unresolvedImportCount
        self.unanalysedLanguages = unanalysedLanguages
        self.limitations = limitations
    }

    /// Did Icarus find an arrangement at all?
    public var isEmpty: Bool { components.isEmpty && mostDependedOnFiles.isEmpty }

    /// What to show when nothing was found — which is never "no structure".
    public var emptyExplanation: String {
        if !unanalysedLanguages.isEmpty {
            return "Icarus doesn’t analyse \(unanalysedLanguages.joined(separator: ", ")) "
                 + "imports, so it didn’t look for structure here. That isn’t a claim "
                 + "that there is none."
        }
        return "No internal imports resolved, so there is nothing to show. That can be "
             + "true of a project whose code lives in one flat package."
    }
}
