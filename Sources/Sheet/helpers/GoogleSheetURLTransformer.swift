import Foundation
import CoreExtensions

public struct GoogleSheetURLTransformer: Sendable {

    public static func transformToCSV(_ urlString: String) throws -> String {
        let trimmedURL = urlString.trimmedContent
        
        guard trimmedURL.isGoogleSheetsURL else {
            throw SheetLocalizerError.invalidGoogleSheetsURL(url: urlString)
        }
        
        if trimmedURL.hasSuffix("/pub?output=csv") {
            return trimmedURL
        }
        
        if trimmedURL.hasSuffix("/pubhtml") {
            return trimmedURL.replacingOccurrences(of: "/pubhtml", with: "/pub?output=csv")
        }
        
        return trimmedURL
    }
}
