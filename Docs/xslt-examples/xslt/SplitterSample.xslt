<?xml version="1.0" encoding="UTF-8"?>
<!--
	Splitting an EAR XML file into many single topic files, with metadata and content, using the ERulesId as file name prefix
	NOTE: Use output from the RemovePartsAndElements-WithContent.xslt as input for this XSLT
	Demonstration sample XSLT
-->
<xsl:stylesheet 
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:er="http://www.easa.europa.eu/erules-export"
    exclude-result-prefixes="xs"
    version="2.0">
    
    <xsl:template match="/">
        <xsl:apply-templates/>
    </xsl:template>
    
    <xsl:template match="er:document|er:toc|er:heading">
        <xsl:apply-templates/>
    </xsl:template>
    
    <xsl:template match="er:topic">
        <xsl:variable name="file-id" select="@ERulesId"/>
        <xsl:result-document href="{concat($file-id,'.xml')}">
            <xsl:copy-of select="."/>            
        </xsl:result-document>
    </xsl:template>
    
</xsl:stylesheet>