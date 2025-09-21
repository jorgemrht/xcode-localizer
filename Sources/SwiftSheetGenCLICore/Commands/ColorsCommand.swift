import Foundation
import SheetLocalizer
import ArgumentParser
import CoreExtensions
import os.log

public struct ColorsCommand: AsyncParsableCommand, SheetGenCommand {

    public typealias ConfigType = ColorConfig
    public typealias GeneratorType = ColorGenerator

    public static let configuration = CommandConfiguration(
        commandName: "colors",
        abstract: "Generate Swift color assets from Google Sheets data"
    )

    public var commandSpecificDirectoryName: String { "Colors" }

    public static let logger = Logger.cli

    @OptionGroup public var sharedOptions: SharedOptions

    public init() {}

    public func createConfiguration() throws -> ColorConfig {
        try validateAndLogGoogleSheetsURL()

        let trimmedBaseDirectory = sharedOptions.outputDir.trimmingCharacters(in: .whitespacesAndNewlines)
        let outputDir = "\(trimmedBaseDirectory)/\(commandSpecificDirectoryName)"

        return ColorConfig.custom(
            outputDirectory: outputDir,
            csvFileName: "colors.csv",
            cleanupTemporaryFiles: !sharedOptions.keepCSV
        )
    }

    public func createGenerator(config: ColorConfig) -> ColorGenerator {
        ColorGenerator(config: config)
    }

}
