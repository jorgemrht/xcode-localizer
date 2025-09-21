import Foundation
import SheetLocalizer
import ArgumentParser
import CoreExtensions
import os.log

public struct LocalizationCommand: AsyncParsableCommand, SheetGenCommand {

    public typealias ConfigType = LocalizationConfig
    public typealias GeneratorType = LocalizationGenerator

    public static let configuration = CommandConfiguration(
        commandName: "localization",
        abstract: "Generate Swift localization code from Google Sheets data"
    )

    public var commandSpecificDirectoryName: String { "Localizables" }

    public static let logger = Logger.cli

    @OptionGroup public var sharedOptions: SharedOptions

    @Option(name: .long, help: "Name for the generated Swift localization enum (default: L10n)")
    public var swiftEnumName: String = "L10n"

    @Flag(name: .long, help: "Generate Swift enum file separate from localization directories")
    public var enumSeparateFromLocalizations: Bool = false

    @Flag(name: .long, help: "Use modern Xcode Strings Catalog (.xcstrings) for localization")
    public var useStringsCatalog: Bool = false

    public init() {}

    public func createConfiguration() throws -> LocalizationConfig {
        try validateAndLogGoogleSheetsURL()

        let trimmedBaseDirectory = sharedOptions.outputDir.trimmingCharacters(in: .whitespacesAndNewlines)
        let outputDir = "\(trimmedBaseDirectory)/\(commandSpecificDirectoryName)"

        return LocalizationConfig.custom(
            outputDirectory: outputDir,
            enumName: swiftEnumName,
            sourceDirectory: enumSeparateFromLocalizations ? trimmedBaseDirectory : outputDir,
            csvFileName: "localizables.csv",
            cleanupTemporaryFiles: !sharedOptions.keepCSV,
            unifiedLocalizationDirectory: !enumSeparateFromLocalizations,
            useStringsCatalog: useStringsCatalog
        )
    }

    public func createGenerator(config: LocalizationConfig) -> LocalizationGenerator {
        LocalizationGenerator(config: config)
    }

}
