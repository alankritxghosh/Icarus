import XCTest
@testable import IcarusKit

/// `GET /map` decoding. The map is what the tour opens with, so a decode
/// failure here would blank the first thing a user ever sees.
@MainActor
final class RepoMapTests: XCTestCase {

    private let json = """
    {"repo":"simonw/sqlite-utils","commit":"abc123",
     "indexed_file_count":18,
     "indexed_languages":{"Python":16,"Markdown":2},
     "indexed_directories":{"sqlite_utils":16,".":2},
     "indexed_documentation":{"files":["README.md","docs/cli.md"],"readme":"README.md"},
     "indexed_entry_points":[{"path":"sqlite_utils/cli.py",
        "rules":[{"rule":"pyproject-console-script","evidence_ref":"config:pyproject.toml",
                  "detail":"declares the console script \\"sqlite-utils\\""}]}],
     "indexed_chunks_by_source":{"code":470,"pr":141},
     "lexical_search_ready":true,"semantic_indexing_in_progress":false,
     "corpus_truncated":false,
     "exclusion_rules":["Directories skipped anywhere in a path: .git, node_modules."],
     "limitations":["This map describes what Icarus INDEXED."]}
    """.data(using: .utf8)!

    func testDecodesTheWholeMap() throws {
        let map = try JSONDecoder().decode(RepoMap.self, from: json)
        XCTAssertEqual(map.repo, "simonw/sqlite-utils")
        XCTAssertEqual(map.indexedFileCount, 18)
        XCTAssertEqual(map.indexedLanguages["Python"], 16)
        XCTAssertEqual(map.indexedDocumentation.readme, "README.md")
        XCTAssertEqual(map.indexedEntryPoints.first?.path, "sqlite_utils/cli.py")
        XCTAssertEqual(map.indexedEntryPoints.first?.rules.first?.rule, "pyproject-console-script")
        XCTAssertEqual(map.indexedEntryPoints.first?.rules.first?.evidenceRef, "config:pyproject.toml")
        XCTAssertFalse(map.corpusTruncated)
        XCTAssertFalse(map.limitations.isEmpty)
    }

    func testAMissingReadmeDecodesAsNilNotAsEmptyString() throws {
        // "no README was indexed" is a fact about the corpus; it must reach the
        // view as an absence it can state, not as a blank it might hide.
        let noReadme = """
        {"repo":"a/b","commit":"c","indexed_file_count":1,"indexed_languages":{},
         "indexed_directories":{},"indexed_documentation":{"files":[],"readme":null},
         "indexed_entry_points":[],"indexed_chunks_by_source":{},
         "lexical_search_ready":true,"semantic_indexing_in_progress":false,
         "corpus_truncated":false,"exclusion_rules":[],"limitations":[]}
        """.data(using: .utf8)!
        let map = try JSONDecoder().decode(RepoMap.self, from: noReadme)
        XCTAssertNil(map.indexedDocumentation.readme)
        XCTAssertTrue(map.indexedEntryPoints.isEmpty)
    }

    func testLanguagesAndDirectoriesSortBiggestFirstDeterministically() throws {
        let map = try JSONDecoder().decode(RepoMap.self, from: json)
        XCTAssertEqual(map.languagesByFileCount.map(\.name), ["Python", "Markdown"])
        XCTAssertEqual(map.directoriesByFileCount.map(\.name), ["sqlite_utils", "."])
    }

    func testTiesBreakOnNameSoTheOrderIsStableBetweenRenders() throws {
        let map = RepoMap(repo: nil, commit: nil, indexedFileCount: 4,
                          indexedLanguages: ["Zig": 2, "Ada": 2],
                          indexedDirectories: [:],
                          indexedDocumentation: IndexedDocumentation(files: [], readme: nil),
                          indexedEntryPoints: [], indexedChunksBySource: [:],
                          lexicalSearchReady: true, semanticIndexingInProgress: false,
                          corpusTruncated: false, exclusionRules: [], limitations: [])
        XCTAssertEqual(map.languagesByFileCount.map(\.name), ["Ada", "Zig"])
    }

    // MARK: auxiliary trees

    func testAuxiliaryShareDecodesWhenPresent() throws {
        let json = Data("""
        {"repo":"a/b","commit":"c","indexed_file_count":500,
         "indexed_languages":{"Python":115},"indexed_directories":{"evals":348},
         "indexed_documentation":{"files":["README.md"],"readme":"README.md"},
         "indexed_entry_points":[],
         "indexed_auxiliary":{"file_count":348,"rule":"files under fixtures/"},
         "indexed_chunks_by_source":{"code":500},
         "lexical_search_ready":true,"semantic_indexing_in_progress":false,
         "corpus_truncated":false,"exclusion_rules":["r"],"limitations":["l"]}
        """.utf8)
        let map = try JSONDecoder().decode(RepoMap.self, from: json)
        XCTAssertEqual(map.indexedAuxiliary?.fileCount, 348)
        XCTAssertFalse(map.indexedAuxiliary?.rule.isEmpty ?? true)
        // Counted WITHIN the totals, never subtracted from them.
        XCTAssertEqual(map.indexedFileCount, 500)
    }

    func testAnOlderBrainWithoutTheFieldStillDecodes() throws {
        // The deployed brain predates this field, and the installed app must
        // keep working against it -- a required field here would surface to a
        // user as "couldn't reach the brain".
        let json = Data("""
        {"repo":"a/b","commit":"c","indexed_file_count":2,
         "indexed_languages":{"Python":2},"indexed_directories":{".":2},
         "indexed_documentation":{"files":[],"readme":null},
         "indexed_entry_points":[],"indexed_chunks_by_source":{"code":2},
         "lexical_search_ready":true,"semantic_indexing_in_progress":false,
         "corpus_truncated":false,"exclusion_rules":[],"limitations":[]}
        """.utf8)
        let map = try JSONDecoder().decode(RepoMap.self, from: json)
        XCTAssertNil(map.indexedAuxiliary)
    }
}
