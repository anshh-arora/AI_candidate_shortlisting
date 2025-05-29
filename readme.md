# 🎯 AI Resume Shortlisting Tool

An intelligent resume screening and candidate shortlisting application powered by Claude AI. This tool automatically processes resumes, extracts candidate information, and ranks candidates against job requirements with detailed explanations.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Claude AI](https://img.shields.io/badge/Claude-AI-orange?style=for-the-badge)

## 🌟 Features

### 🤖 **AI-Powered Processing**
- **Smart Resume Parsing**: Extracts structured data from PDF/DOC files using Claude AI
- **Intelligent Candidate Scoring**: Matches candidates against job requirements with detailed analysis
- **Batch Processing**: Efficiently processes multiple resumes in batches of 10
- **Advanced Ranking**: Ranks candidates with comprehensive explanations

### 📊 **Comprehensive Analysis**
- **Customizable Scoring Weights**: Adjust importance of experience, skills, education, and certifications
- **Detailed Score Breakdowns**: Component-wise scoring with explanations
- **Additional Preferences**: Factor in specific hiring preferences beyond job description
- **Top 5 Candidate Showcase**: Beautiful visual display of best candidates

### 📈 **Professional Reports**
- **Multi-format Downloads**: Excel, CSV, and JSON export options
- **Comprehensive Excel Reports**: Multi-sheet reports with candidates, analysis, and job info
- **Structured Candidate Database**: Organized candidate information for easy review
- **Top Performers Analysis**: Detailed breakdown of highest-scoring candidates

## 🚀 Quick Deployment Guide

### **Option 1: Deploy to Streamlit Cloud (Recommended)**

1. **Fork this repository** to your GitHub account

2. **Set up Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with your GitHub account
   - Click "New app"
   - Select your forked repository
   - Set **main file** as `main.py`
   - Click "Deploy"

3. **Add API Key:**
   - In Streamlit Cloud dashboard, go to your app settings
   - Click "Secrets"
   - Add your secrets:
   ```toml
   ANTHROPIC_API_KEY = "your_claude_api_key_here"
   CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
   ```

4. **Your app is live!** 🎉

### **Option 2: Local Development**

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd resume-shortlisting-tool
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file:
   ```env
   ANTHROPIC_API_KEY=your_claude_api_key_here
   CLAUDE_MODEL=claude-3-5-sonnet-20241022
   ```

4. **Run the application:**
   ```bash
   streamlit run main.py
   ```

## 🔑 Getting Claude API Key

1. **Visit** [Anthropic Console](https://console.anthropic.com/)
2. **Sign up** or log in to your account
3. **Navigate** to the API Keys section
4. **Create** a new API key
5. **Copy** the key and add it to your deployment

## 📱 How to Use

### **Tab 1: Upload & Process**
1. **Upload Resumes**: Drop PDF, DOC, or DOCX files
2. **Enter Job Details**: 
   - Job title for file naming
   - Complete job description with requirements
   - Additional hiring preferences (optional)
3. **Adjust Scoring Weights**: Use sidebar to customize criteria importance
4. **Start Processing**: Click the button and watch AI analyze candidates

### **Tab 2: Candidate Details**
- **View All Extracted Data**: See structured candidate information
- **Download Options**: 
  - 📊 Excel file with all candidate data
  - 📄 JSON file with raw extracted data
- **Data Review**: Verify extraction accuracy before shortlisting

### **Tab 3: Shortlisted Candidates**
- **Top 5 Showcase**: Visual cards with best candidates
- **Detailed Analysis**: Expandable sections with full explanations
- **Complete Candidate List**: Ranked table of all candidates
- **Multiple Downloads**:
  - 🏆 Top 5 candidates CSV
  - 📊 All candidates CSV
  - 📈 Complete Excel report

## ⚙️ Scoring System

The application evaluates candidates across four key dimensions:

| **Criteria** | **Default Weight** | **Description** |
|--------------|-------------------|----------------|
| **Experience** | 30% | Years and relevance of work experience |
| **Skills** | 40% | Technical and soft skills alignment |
| **Education** | 20% | Educational background relevance |
| **Certifications** | 10% | Professional certifications value |

*All weights are fully customizable and automatically normalized*

## 📊 Sample Output

### **Top Candidate Card Example:**
```
🏆 #1: John Smith
📊 87.5% Match
📧 john.smith@email.com
📱 +1-555-0123
💼 5 years experience
🎯 HIGHLY_RECOMMENDED
```

### **Detailed Analysis:**
- **Why this candidate**: Excellent match with 5+ years in required technologies...
- **Key Strengths**: Full-stack expertise, leadership experience, cloud platforms
- **Score Breakdown**: Experience: 90% | Skills: 85% | Education: 88% | Certs: 75%

## 🏗️ Project Structure

```
resume-shortlisting-tool/
├── main.py              # Main Streamlit application
├── requirements.txt     # Python dependencies
├── .gitignore          # Git ignore rules
├── README.md           # This file
└── .streamlit/         # Streamlit configuration (auto-created)
```

## 🔧 Technical Features

### **AI Integration**
- Uses Claude 3.5 Sonnet for optimal accuracy
- Robust error handling and fallback mechanisms
- Rate limiting protection for API calls
- JSON parsing with multiple fallback strategies

### **File Processing**
- Supports PDF, DOC, and DOCX formats
- Robust text extraction with error recovery
- Experience extraction from filename patterns
- Metadata preservation for tracking

### **Data Management**
- Memory-efficient processing of large batches
- Structured data conversion for analysis
- Multi-format export capabilities
- Session state management for user experience

## 🚨 Important Notes

1. **API Costs**: Each resume requires API calls - monitor your Claude usage
2. **File Quality**: Well-formatted resumes yield better extraction results
3. **Job Descriptions**: Detailed descriptions improve matching accuracy
4. **Privacy**: Data is processed in-memory only, not stored permanently
5. **Accuracy**: AI results should be reviewed by human recruiters

## 📈 Performance Tips

- **Batch Size**: Processes 10 candidates at a time for optimal performance
- **File Size**: Keep resume files under 5MB for best results
- **Description Quality**: Detailed job descriptions improve matching accuracy
- **Weight Tuning**: Adjust scoring weights based on role requirements

## 🐛 Troubleshooting

### **Common Issues:**

**❌ API Key Error**
```
Error: Please set your ANTHROPIC_API_KEY
```
*Solution: Check your API key in Streamlit secrets or .env file*

**❌ File Processing Error**
- Ensure files are not password-protected
- Check file format is supported (PDF, DOC, DOCX)
- Try with smaller file sizes

**❌ Zero Scores Issue**
- Verify job description is meaningful (not just "dfewfw")
- Check that resume content was extracted properly
- Review API response in terminal logs

**❌ Deployment Issues**
- Verify all files are in repository
- Check requirements.txt is complete
- Ensure API key is set in Streamlit secrets

### **Debug Mode**
- Terminal shows JSON output for each processed resume
- Check console for detailed extraction data
- Monitor API call success/failure rates

## 🔄 Updates & Maintenance

### **Regular Updates:**
- Monitor Claude API version updates
- Update dependencies quarterly
- Review and optimize prompts based on results
- Add new file format support as needed

### **Performance Monitoring:**
- Track API usage costs
- Monitor processing success rates
- User feedback integration
- Error rate analysis

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:
- 📧 Create an issue in this repository
- 💬 Check existing issues for solutions
- 📚 Review the troubleshooting section above
