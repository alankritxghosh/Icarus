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

    enum CodingKeys: String, CodingKey {
        case repo, commit, limitations
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
                corpusTruncated: Bool, exclusionRules: [String], limitations: [String]) {
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
