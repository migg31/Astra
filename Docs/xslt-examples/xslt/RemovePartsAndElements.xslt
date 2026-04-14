<?xml version="1.0" encoding="UTF-8"?>
<!--
	Remove unwanted parts and elements 
	Demonstration sample XSLT
-->

<xsl:stylesheet version="1.0" 
	xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
	xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
	xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage"
	xmlns:er="http://www.easa.europa.eu/erules-export"
	exclude-result-prefixes="w pkg er"
	>
	
	<xsl:output method="xml" encoding="UTF-8" omit-xml-declaration="yes" indent="yes"/>
	<xsl:strip-space elements="*"/>
	
	<xsl:template match="pkg:package">
		<!-- we start by creating a root element, ear-document, to encapsulate the two parts of the output: the metadata and the content -->
		<ear-document>
			<xsl:apply-templates/>
		</ear-document>
	</xsl:template>

	<xsl:template match="pkg:part">
		<xsl:choose>
			<!-- Here, we want to choose the two parts containing the EASA metadata (er:document) and the Word content (w:document), respectively. All other parts 
				are removed. The safe way to select a particular part in the package is to pick the part with the right descendant (children, 
				granchildren, etc) instead of using the part names. This is because at least some part names can change from 
				document to document. -->
			<xsl:when test="descendant::er:document">
				<xsl:apply-templates select="//er:document"/>
			</xsl:when>
			<xsl:when test="descendant::w:document">
				<w:document>
					<!-- we are only interested in the content inside w:sdt elements, not the frontmatter or backmatter, so we 
						select //sdt for processing -->
					<xsl:apply-templates select="//w:sdt"/>
				</w:document>
			</xsl:when>
			<xsl:otherwise>
				<!-- delete other (unwanted) parts by doing nothing here -->
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	
	<xsl:template match="w:sdt">
		<xsl:variable name="type" select="w:sdtPr/w:alias/@w:val"/>
		<xsl:variable name="id" select="w:sdtPr/w:id/@w:val"></xsl:variable>
		<xsl:choose>
			<xsl:when test="$type='topic'">
				<topic>
					<xsl:attribute name="id"><xsl:value-of select="$id"/></xsl:attribute>
					<xsl:apply-templates select="w:sdtContent"/>
				</topic>				
			</xsl:when>
			<xsl:otherwise>
				<!-- delete by doing nothing -->
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	
	<xsl:template match="w:sdtContent">
		<!-- when processing the sdt content, only w:p elements (representing paragraphs) are selected. For example Tables are disregarded in 
		this example-->
		<xsl:apply-templates select="w:p"/>
	</xsl:template>
	
	<xsl:template match="w:p">
		<xsl:if test="not(normalize-space(.)='')">
		<!-- inside w:p, only the text content is preserved, any possible styling information or 
		links, etc. are ignored in this example-->
			<para><xsl:value-of select="normalize-space(.)"/></para>
		</xsl:if>
	</xsl:template>
	
	<xsl:template match="@* | * | processing-instruction() | comment()">
	<!-- this templates just copies any kind of element and attribute that is not handled above -->
		<xsl:copy>
			<xsl:apply-templates select="* | @* | text() | processing-instruction() | comment()"/>
		</xsl:copy>
	</xsl:template>
	
</xsl:stylesheet>
