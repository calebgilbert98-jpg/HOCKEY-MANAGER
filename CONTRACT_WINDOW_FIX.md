# Contract Negotiation Window - Fixed Text Readability

## Problem Fixed
The contract negotiations screen had unreadable text due to poor styling and layout.

## Changes Made

### Visual Improvements
- **Increased window size** from 400x300 to 500x450 pixels
- **Applied proper dark theme styling** using consistent `TLabel`, `Title.TLabel`, and `Subtitle.TLabel` styles
- **Organized layout** with labeled sections and proper spacing
- **Added modal behavior** with `transient()` and `grab_set()`

### Content Enhancements
- **Player Information Section**: Shows name, position, age, overall rating, and potential
- **Current Contract Section**: Displays existing contract details for extensions
- **Contract Offer Section**: Organized input fields with clear labels
- **Real-time Total Calculation**: Shows total contract value as user types
- **Professional Button Layout**: Cancel and Submit buttons properly positioned

### Functionality Improvements
- **Enhanced Input Validation**: Checks for valid salary range and contract length (1-8 years)
- **Better Error Messages**: Clear feedback for invalid inputs
- **Comma Support**: Handles salary input with or without commas
- **Extension vs New Contract**: Different titles and layouts for contract types

### Code Quality
- **Consistent Styling**: Uses same style system as rest of application
- **Proper Error Handling**: Try/catch blocks for input validation
- **Dynamic Updates**: Real-time calculation updates via variable tracing
- **Clean Code Structure**: Well-organized methods and clear variable names

## Testing
To test the improvements:
1. Run `python main.py`
2. Select a team and go to Roster Management
3. Right-click any player and select "Negotiate Extension" or "Offer Contract"
4. Verify text is readable and layout is professional

## Result
The contract negotiation window now has:
✅ **Fully readable text** with proper dark theme colors
✅ **Professional layout** with organized sections
✅ **Better user experience** with real-time feedback
✅ **Consistent styling** matching the rest of the application