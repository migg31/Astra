<?xml version="1.0" encoding="UTF-8"?>
<!--
	Remove unwanted parts and elements and bring metadata and content together
	Demonstration sample XSLT
-->

<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
	xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
	xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage"
	xmlns:er="http://www.easa.europa.eu/erules-export"
	exclude-result-prefixes="w pkg er" >
	
	<xsl:output method="xml" encoding="UTF-8" omit-xml-declaration="yes" indent="yes"/>

	<xsl:strip-space elements="*"/>
	
	<xsl:template match="pkg:package">
			<xsl:apply-templates/>
	</xsl:template>

	<xsl:template match="pkg:part">
		<xsl:choose>
			<xsl:when test="descendant::er:document">
				<xsl:apply-templates select="//er:document"/>				
			</xsl:when>
			<xsl:otherwise>
				<!-- delete other parts by doing nothing here -->
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	
	<xsl:template match="er:document | er:toc | er:heading">
		<xsl:copy>
			<xsl:apply-templates select="@*"/>
			<xsl:apply-templates/>
		</xsl:copy>
	</xsl:template>
	
	<xsl:template match="er:topic">
		<xsl:variable name="sdt-id" select="@sdt-id"/>
		<xsl:copy>
			<xsl:apply-templates select="@*"/>
			<content>
				<xsl:for-each select="//w:sdt[w:sdtPr/w:id/@w:val=$sdt-id]/w:sdtContent/w:p">
					<xsl:if test="not(normalize-space(.)='')">
						<para><xsl:value-of select="normalize-space(.)"/></para>
					</xsl:if>	
				</xsl:for-each>
			</content>
		</xsl:copy>
		<content/>
	</xsl:template>
	
	<xsl:template match="@* | * ">
		<xsl:copy>
			<xsl:apply-templates select="* | @* | text() | processing-instruction() | comment()"/>
		</xsl:copy>
	</xsl:template>

</xsl:stylesheet>
