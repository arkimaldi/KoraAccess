const fs = require('fs');
const path = require('path');

const targetDir = './src/app'; // Your source directory
const outputFilePath = './src/assets/i18n/en.json'; // The output path for your translation file

const translationKeys = new Set(); // Use a Set to avoid duplicates

function extractTranslations(dir) {
    const files = fs.readdirSync(dir);
    
    files.forEach(file => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);
        
        if (stat.isDirectory()) {
            extractTranslations(filePath); // Recursively search directories
        } else if (filePath.endsWith('.html') || filePath.endsWith('.ts')) {
            const content = fs.readFileSync(filePath, 'utf-8');
            const matches = content.match(/{{\s*['"`]([^'"`]+)['"`]?\s*\| translate\s*}}/g);
            if (matches) {
                matches.forEach(match => {
                    // Now we need to extract the key from each match
                    const keyMatch = match.match(/['"`]([^'"`]+)['"`]?/); // Capture the key inside the quotes
            
                    if (keyMatch && keyMatch[1]) {
                        const key = keyMatch[1];  // Access the capturing group
                        translationKeys.add(key);  // Add the key to the Set
                    } else {
                        console.log("No key found for match: ", match);
                    }
                });
            }
        }
    });
}

// Start the extraction process
extractTranslations(targetDir);

// Write the output to a JSON file
const translations = {};
translationKeys.forEach(key => {
    translations[key] = key; // Defaulting the value to the key itself; change as needed
});

const sortedTranslations = Object.keys(translations)
    .sort()
    .reduce((obj, key) => {
        obj[key] = translations[key];
        return obj;
    }, {});

fs.writeFileSync(outputFilePath, JSON.stringify(sortedTranslations, null, 4), 'utf-8');

console.log(`Translations extracted to ${outputFilePath}`);
