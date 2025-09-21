import Foundation
import XcodeIntegration
import CoreExtensions
import os.log

public struct ColorGenerator: Sendable {
    
    private let config: ColorConfig
    private let csvProcessor: ColorCSVProcessor
    private static let logger = Logger.colorGenerator

    public init(config: ColorConfig = .default) {
        self.config = config
        self.csvProcessor = ColorCSVProcessor()
    }

    public func generate(from csvPath: String) async throws {
        try Task.checkCancellation()
        
        let rows = try await csvProcessor.parse(csvPath: csvPath)
        try csvProcessor.validate(rows: rows)
        
        guard rows.count > 3 else {
            throw SheetLocalizerError.insufficientData
        }
        
        let colorEntries = try csvProcessor.process(rows: rows)
        
        guard !colorEntries.isEmpty else {
            throw SheetLocalizerError.csvParsingError("No valid color entries found")
        }
        
        
        try await generateColorsFile(entries: colorEntries)
        try await generateColorDynamicFile()
        
        try await handleXcodeIntegration()
        
        if config.cleanupTemporaryFiles {
            try await cleanupTemporaryCSV(at: csvPath)
        }
    }

    private func generateColorsFile(entries: [ColorEntry]) async throws {
        let outputPath = "\(config.outputDirectory)/Colors.swift"
        let generator = ColorFileGenerator()
        let code = generator.generateCode(entries: entries)
        let url = URL(fileURLWithPath: outputPath)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try code.write(to: url, atomically: true, encoding: .utf8)
    }

    private func generateColorDynamicFile() async throws {
        let outputPath = "\(config.outputDirectory)/Color+Dynamic.swift"
        let generator = ColorDynamicFileGenerator()
        let code = generator.generateCode()
        let url = URL(fileURLWithPath: outputPath)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try code.write(to: url, atomically: true, encoding: .utf8)
    }

    private func handleXcodeIntegration() async throws {
        if isTuistProject() {
            return
        }
        
        guard let projectPath = try GeneratorHelper.findXcodeProjectPath(logger: Self.logger) else {
            return
        }
        
        let colorsPath = "\(config.outputDirectory)/Colors.swift"
        let dynamicPath = "\(config.outputDirectory)/Color+Dynamic.swift"
        
        try await XcodeIntegration.addColorFiles(
            projectPath: projectPath,
            colorsPath: colorsPath,
            dynamicPath: dynamicPath
        )
        
    }
    
    private func cleanupTemporaryCSV(at csvPath: String) async throws {
        try await GeneratorHelper.cleanupTemporaryFile(at: csvPath, logger: Self.logger)
    }

    private func isTuistProject() -> Bool {
        let tuistFiles = ["Project.swift", "Workspace.swift", "Tuist/Project.swift", "Tuist/Workspace.swift", ".tuist-version"]
        return tuistFiles.contains { FileManager.default.fileExists(atPath: $0) }
    }
    

}

struct ColorCSVProcessor: Sendable {
    private static let logger = Logger.colorGenerator
    
    func parse(csvPath: String) async throws -> [[String]] {
        let content = try String(contentsOfFile: csvPath, encoding: .utf8)
        return try CSVParser.parse(content)
    }
    
    func validate(rows: [[String]]) throws {
        guard rows.count >= 2 else {
            throw SheetLocalizerError.csvParsingError("CSV must have at least 2 rows")
        }

        var foundValidHeader = false
        
        for row in rows {
            if row.count >= 6 &&
               row[1].trimmedContent == ColorHeader.name.rawValue &&
               row[2].trimmedContent == ColorHeader.anyHex.rawValue &&
               row[3].trimmedContent == ColorHeader.lightHex.rawValue &&
               row[4].trimmedContent == ColorHeader.darkHex.rawValue {
                foundValidHeader = true
                break
            }
        }

        guard foundValidHeader else {
            throw SheetLocalizerError.csvParsingError("Invalid CSV structure - missing required headers")
        }
    }
    
    func process(rows: [[String]]) throws -> [ColorEntry] {
        guard rows.count > 1 else {
            throw SheetLocalizerError.csvParsingError("CSV must have at least 2 rows")
        }
        
        var headerRowIndex = -1
        
        for (index, row) in rows.enumerated() {
            if row.count > 5 &&
               row[1].trimmedContent == ColorHeader.name.rawValue &&
               row[2].trimmedContent == ColorHeader.anyHex.rawValue &&
               row[3].trimmedContent == ColorHeader.lightHex.rawValue &&
               row[4].trimmedContent == ColorHeader.darkHex.rawValue {
                headerRowIndex = index
                break
            }
        }
        
        guard headerRowIndex >= 0 else {
            throw SheetLocalizerError.csvParsingError("Header row not found")
        }

        var entries: [ColorEntry] = []

        for row in rows.dropFirst(headerRowIndex + 1) {
            if row.count < 6 { continue }

            let firstCol = row.first?.trimmedContent ?? ""

            if firstCol == "[END]" { break }
            if firstCol == "[COMMENT]" || firstCol.hasPrefix("[") { continue }

            let name = row[1].trimmedContent
            let anyHex = row[2].trimmedContent
            let lightHex = row[3].trimmedContent
            let darkHex = row[4].trimmedContent

            guard !name.isEmpty else {
                continue
            }
            
            guard !name.hasPrefix("[") else {
                continue
            }

            if anyHex.isEmpty && lightHex.isEmpty && darkHex.isEmpty {
                continue
            }

            entries.append(ColorEntry(
                name: name,
                anyHex: anyHex.isEmpty ? nil : anyHex,
                lightHex: lightHex.isEmpty ? nil : lightHex,
                darkHex: darkHex.isEmpty ? nil : darkHex
            ))
        }
        
        return entries
    }
}
