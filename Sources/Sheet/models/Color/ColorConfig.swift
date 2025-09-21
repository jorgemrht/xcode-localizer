import Foundation

public struct ColorConfig: SheetConfig {
    public let outputDirectory: String
    public let csvFileName: String
    public let cleanupTemporaryFiles: Bool
    
    public init(
        outputDirectory: String,
        csvFileName: String,
        cleanupTemporaryFiles: Bool
    ) {
        self.outputDirectory = outputDirectory
        self.csvFileName = csvFileName
        self.cleanupTemporaryFiles = cleanupTemporaryFiles
    }
    
    public static let `default` = ColorConfig(
        outputDirectory: "Colors",
        csvFileName: "colors.csv",
        cleanupTemporaryFiles: true
    )
    
    public static func custom(
        outputDirectory: String,
        csvFileName: String = "colors.csv",
        cleanupTemporaryFiles: Bool = true
    ) -> Self {
        ColorConfig(
            outputDirectory: outputDirectory,
            csvFileName: csvFileName,
            cleanupTemporaryFiles: cleanupTemporaryFiles
        )
    }
}