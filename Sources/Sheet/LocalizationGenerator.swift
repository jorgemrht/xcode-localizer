import Foundation
import XcodeIntegration
import CoreExtensions
import os.log

public struct LocalizationGenerator: Sendable {
    
    private let config: LocalizationConfig
    private let csvProcessor: LocalizationCSVProcessor
    private static let logger = Logger.localizationGenerator
    
    public init(config: LocalizationConfig = .default) {
        self.config = config
        self.csvProcessor = LocalizationCSVProcessor()
    }

    public func generate(from csvPath: String) async throws {
        try Task.checkCancellation()
        
        let rows = try await csvProcessor.parse(csvPath: csvPath)
        try csvProcessor.validate(rows: rows)
        
        guard rows.count > 3 else {
            throw SheetLocalizerError.insufficientData
        }
        
        let (languages, entries) = try csvProcessor.process(rows: rows)
        
        guard !languages.isEmpty else {
            throw SheetLocalizerError.csvParsingError("No valid languages were found")
        }
        
        guard !entries.isEmpty else {
            throw SheetLocalizerError.csvParsingError("No valid entries found")
        }
        
        
        if config.useStringsCatalog {
            try await generateStringsCatalog(languages: languages, entries: entries)
        } else {
            try await generateLocalizationFiles(languages: languages, entries: entries)
            let allKeys = Set(entries.map(\.key)).sorted()
            try await generateSwiftEnum(allKeys: allKeys)
        }
        
        try await handleXcodeIntegration(languages: languages)
        
        if config.cleanupTemporaryFiles {
            try await cleanupTemporaryCSV(at: csvPath)
        }
    }

    private func generateStringsCatalog(languages: [String], entries: [LocalizationEntry]) async throws {
        let sourceLanguage = languages.first ?? "en"
        let catalogData = try StringsCatalogGenerator.generate(
            for: entries,
            sourceLanguage: sourceLanguage,
            developmentRegion: sourceLanguage
        )
        
        let outputPath = "\(config.outputDirectory)/Localizable.xcstrings"
        let url = URL(fileURLWithPath: outputPath)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try catalogData.write(to: url)
    }

    private func generateLocalizationFiles(languages: [String], entries: [LocalizationEntry]) async throws {
        for language in languages {
            try Task.checkCancellation()
            try await generateLanguageFile(language: language, entries: entries)
        }
    }

    private func generateLanguageFile(language: String, entries: [LocalizationEntry]) async throws {
        let folder = "\(config.outputDirectory)/\(language).lproj"
        let filePath = "\(folder)/Localizable.strings"
        
        let validEntries = entries
            .filter { $0.hasTranslation(for: language) }
            .sorted { $0.key < $1.key }
        
        var lines: [String] = []
        lines.reserveCapacity(validEntries.count)
        
        for entry in validEntries {
            guard let translation = entry.translation(for: language) else { continue }
            
            let formattedTranslation = formatTranslation(translation)
            let escaped = formattedTranslation
                .replacingOccurrences(of: "\"", with: "\\\"")
                .replacingOccurrences(of: "\n", with: "\\n")
            
            lines.append("\"\(entry.key)\" = \"\(escaped)\";")
        }
        
        let content = lines.joined(separator: "\n")
        let url = URL(fileURLWithPath: filePath)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try content.write(to: url, atomically: true, encoding: .utf8)
    }

    private func generateSwiftEnum(allKeys: [String]) async throws {
        let outputPath = "\(config.sourceDirectory)/\(config.enumName).swift"
        let enumGenerator = SwiftEnumGenerator(enumName: config.enumName)
        let code = enumGenerator.generateCode(allKeys: allKeys)
        let url = URL(fileURLWithPath: outputPath)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try code.write(to: url, atomically: true, encoding: .utf8)
    }
    
    private func handleXcodeIntegration(languages: [String]) async throws {
        if isTuistProject() {
            return
        }
        
        guard let projectPath = try GeneratorHelper.findXcodeProjectPath(logger: Self.logger) else {
            return
        }
        
        if config.useStringsCatalog {
            let catalogPath = "\(config.outputDirectory)/Localizable.xcstrings"
            try await XcodeIntegration.addStringsCatalogFile(
                projectPath: projectPath,
                catalogPath: catalogPath
            )
        } else {
            let localizationFiles = languages.map { "\(config.outputDirectory)/\($0).lproj/Localizable.strings" }
            let enumFile = "\(config.sourceDirectory)/\(config.enumName).swift"
            
            try await XcodeIntegration.addLocalizationFiles(
                projectPath: projectPath,
                generatedFiles: localizationFiles,
                languages: languages,
                enumFile: enumFile
            )
        }
    }
    
    private func cleanupTemporaryCSV(at csvPath: String) async throws {
        try await GeneratorHelper.cleanupTemporaryFile(at: csvPath, logger: Self.logger)
    }
    
    private func formatTranslation(_ translation: String) -> String {
        let placeholderPattern = "\\{\\{.*?\\}\\}"
        guard let regex = try? NSRegularExpression(pattern: placeholderPattern) else {
            return translation
        }
        let range = NSRange(translation.startIndex..<translation.endIndex, in: translation)
        return regex.stringByReplacingMatches(
            in: translation,
            options: [],
            range: range,
            withTemplate: "%@"
        )
    }

    private func isTuistProject() -> Bool {
        let tuistFiles = ["Project.swift", "Workspace.swift", "Tuist/Project.swift", "Tuist/Workspace.swift", ".tuist-version"]
        return tuistFiles.contains { FileManager.default.fileExists(atPath: $0) }
    }
    
}

struct LocalizationCSVProcessor: Sendable {
    private static let logger = Logger.localizationGenerator
    
    func parse(csvPath: String) async throws -> [[String]] {
        let content = try String(contentsOfFile: csvPath, encoding: .utf8)
        return try CSVParser.parse(content)
    }
    
    func validate(rows: [[String]]) throws {
        guard rows.count >= 4 else {
            throw SheetLocalizerError.csvParsingError("CSV must have at least 4 rows")
        }
        
        var foundValidHeader = false
        
        for row in rows {
            if row.count >= 5 &&
               row[1].trimmedContent == LocalizationHeader.view.rawValue &&
               row[2].trimmedContent == LocalizationHeader.item.rawValue &&
               row[3].trimmedContent == LocalizationHeader.type.rawValue {
                foundValidHeader = true
                
                let languageColumns = Array(row.dropFirst(4))
                    .map { $0.trimmedContent }
                    .filter { !$0.isEmpty && !$0.hasPrefix("[") }
                
                guard !languageColumns.isEmpty else {
                    throw SheetLocalizerError.csvParsingError("No language columns found")
                }
                
                break
            }
        }
        
        guard foundValidHeader else {
            throw SheetLocalizerError.csvParsingError("Invalid CSV structure - missing required headers")
        }
    }
    
    func process(rows: [[String]]) throws -> ([String], [LocalizationEntry]) {
        guard rows.count > 1 else {
            throw SheetLocalizerError.csvParsingError("CSV must have at least 2 rows")
        }

        var headerRowIndex = -1
        
        for (index, row) in rows.enumerated() {
            if row.count > 4 &&
               row[1].trimmedContent == LocalizationHeader.view.rawValue &&
               row[2].trimmedContent == LocalizationHeader.item.rawValue &&
               row[3].trimmedContent == LocalizationHeader.type.rawValue {
                headerRowIndex = index
                break
            }
        }
        
        guard headerRowIndex >= 0 else {
            throw SheetLocalizerError.csvParsingError("Header row not found")
        }
        
        let header = rows[headerRowIndex]
        guard header.count > 4 else {
            throw SheetLocalizerError.csvParsingError("Header must have at least 5 columns")
        }

        let languages = Array(header.dropFirst(4))
            .map { $0.trimmedContent }
            .filter { !$0.isEmpty && !$0.hasPrefix("[") }

        var entries: [LocalizationEntry] = []
        
        for row in rows.dropFirst(headerRowIndex + 1) {
            if row.count < 5 { continue }
            
            let firstCol = row.first?.trimmedContent.uppercased() ?? ""
            let secondCol = row.count > 1 ? row[1].trimmedContent.uppercased() : ""
            
            if firstCol == "[END]" { break }
            if secondCol == "[COMMENT]" || secondCol.hasPrefix("[") { continue }
            
            guard row.count >= 4 else { continue }
            
            let view = row[1].trimmedContent
            let item = row[2].trimmedContent
            let type = row[3].trimmedContent
            
            guard !view.isEmpty && !item.isEmpty && !type.isEmpty else { continue }
            guard !view.hasPrefix("[") && !item.hasPrefix("[") && !type.hasPrefix("[") else { continue }

            let key = "\(view)_\(item)_\(type)"
            if let reason = key.invalidLocalizationKeyReason, !reason.isEmpty {
                continue
            }
            
            let values = Array(row.dropFirst(4))
            var translations: [String: String] = [:]

            for index in languages.indices {
                if index < values.count {
                    let val = values[index].trimmedContent
                    if !val.isEmpty {
                        translations[languages[index]] = val
                    }
                }
            }

            guard !translations.isEmpty else { continue }

            entries.append(LocalizationEntry(
                view: view,
                item: item,
                type: type,
                translations: translations
            ))
        }

        return (languages, entries)
    }
}
