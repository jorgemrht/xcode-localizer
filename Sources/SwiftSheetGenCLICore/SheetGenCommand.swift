import Foundation
import ArgumentParser
import CoreExtensions
import os.log
import SheetLocalizer

public protocol SheetGenCommand: AsyncParsableCommand {
    
    associatedtype ConfigType: SheetConfig
    associatedtype GeneratorType: SheetGenerator where GeneratorType.Config == ConfigType

    var sharedOptions: SharedOptions { get }
    var commandSpecificDirectoryName: String { get }
    
    static var logger: Logger { get }

    func createConfiguration() throws -> ConfigType
    func createGenerator(config: ConfigType) -> GeneratorType
    
    func executeCompleteWorkflow() async throws
    func downloadCSVDataFromGoogleSheets() async throws
    func generateSwiftFiles(using configuration: ConfigType) async throws
    func temporaryFileCleanupIfRequested() throws
}

public extension SheetGenCommand {
    
    func getOutputDirectory() throws -> String {
        let baseDir = sharedOptions.outputDir.trimmingCharacters(in: .whitespacesAndNewlines)
        return "\(baseDir)/\(commandSpecificDirectoryName)"
    }
    
    func getTemporaryCSVFilePath() throws -> String {
        "\(FileManager.default.currentDirectoryPath)/\(commandSpecificDirectoryName.lowercased())/generated_\(commandSpecificDirectoryName.lowercased()).csv"
    }
    
    func run() async throws {
        
        let executionStartTime = Date()
        let commandName = Self.configuration.commandName ?? ""
        
        Self.logger.log("🚀 SwiftSheetGen \(commandName) generation started")
        
        do {
            try await executeCompleteWorkflow()
            let outputDir = try getOutputDirectory()
            logSuccessfulExecutionCompletion(
                startTime: executionStartTime,
                generatedFilesLocation: outputDir
            )
        } catch {
            Self.logger.error("💥 \(commandName.capitalized) generation workflow failed: \(error.localizedDescription)")
            throw SheetLocalizerError.networkError("Failed to generate \(commandName): \(error.localizedDescription)")
        }
    }

    func executeCompleteWorkflow() async throws {
        
        let commandName = Self.configuration.commandName ?? ""
        
        // Step 1: Validate and prepare configuration
        let configuration = try createConfiguration()
        
        // Step 2: Download CSV data from Google Sheets
        Self.logger.log("📥 Downloading CSV data from Google Sheets")
        try await downloadCSVDataFromGoogleSheets()
        
        // Step 3: Generate Swift files
        Self.logger.log("🔨 Generating Swift \(commandName) files from CSV data")
        try await generateSwiftFiles(using: configuration)
        
        // Step 4: Clean up temporary files if requested
        try temporaryFileCleanupIfRequested()
    }

    func downloadCSVDataFromGoogleSheets() async throws {
        let csvDataDownloader = CSVDownloader()
        
        let csvPath = try getTemporaryCSVFilePath()
        let tempDirectory = (csvPath as NSString).deletingLastPathComponent
        try ensureOutputDirectoryExists(atPath: tempDirectory, logger: Self.logger)

        try await csvDataDownloader.download(
            from: sharedOptions.sheetsURL,
            to: csvPath
        )
    }

    func generateSwiftFiles(using configuration: ConfigType) async throws {
        let generator = createGenerator(config: configuration)
        
        let csvPath = try getTemporaryCSVFilePath()
        try await generator.generate(from: csvPath)
        Self.logger.log("✅ Files generated successfully")
    }

    func temporaryFileCleanupIfRequested() throws {
        let csvPath = try getTemporaryCSVFilePath()
        
        if sharedOptions.keepCSV {
            Self.logger.log("💾 CSV file preserved at: \(csvPath)")
            return
        }
        
        let fileManager = FileManager.default
        if fileManager.fileExists(atPath: csvPath) {
            try? fileManager.removeItem(atPath: csvPath)
        }
    }
}

public extension SheetGenCommand {
    func validateAndLogGoogleSheetsURL() throws {
        guard validateGoogleSheetsURL(sharedOptions.sheetsURL) else {
            throw SheetLocalizerError.invalidURL("Invalid Google Sheets URL: \(sharedOptions.sheetsURL)")
        }
    }
}
