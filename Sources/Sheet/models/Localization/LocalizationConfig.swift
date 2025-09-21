import Foundation

public struct LocalizationConfig: SheetConfig {
    public let outputDirectory: String
    public let enumName: String
    public let sourceDirectory: String
    public let csvFileName: String
    public let cleanupTemporaryFiles: Bool
    public let unifiedLocalizationDirectory: Bool
    public let useStringsCatalog: Bool
    
    public init(
        outputDirectory: String,
        enumName: String,
        sourceDirectory: String,
        csvFileName: String,
        cleanupTemporaryFiles: Bool,
        unifiedLocalizationDirectory: Bool,
        useStringsCatalog: Bool
    ) {
        self.outputDirectory = outputDirectory
        self.enumName = enumName
        self.sourceDirectory = sourceDirectory
        self.csvFileName = csvFileName
        self.cleanupTemporaryFiles = cleanupTemporaryFiles
        self.unifiedLocalizationDirectory = unifiedLocalizationDirectory
        self.useStringsCatalog = useStringsCatalog
    }
    
    public static let `default` = LocalizationConfig(
        outputDirectory: "./",
        enumName: "L10n",
        sourceDirectory: "./",
        csvFileName: "localizables.csv",
        cleanupTemporaryFiles: true,
        unifiedLocalizationDirectory: true,
        useStringsCatalog: false
    )
    
    public static func custom(
        outputDirectory: String,
        enumName: String = "L10n",
        sourceDirectory: String? = nil,
        csvFileName: String = "localizables.csv",
        cleanupTemporaryFiles: Bool = true,
        unifiedLocalizationDirectory: Bool = true,
        useStringsCatalog: Bool = false
    ) -> Self {
        LocalizationConfig(
            outputDirectory: outputDirectory,
            enumName: enumName,
            sourceDirectory: sourceDirectory ?? outputDirectory,
            csvFileName: csvFileName,
            cleanupTemporaryFiles: cleanupTemporaryFiles,
            unifiedLocalizationDirectory: unifiedLocalizationDirectory,
            useStringsCatalog: useStringsCatalog
        )
    }
}
