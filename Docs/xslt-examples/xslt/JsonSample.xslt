<?xml version="1.0" encoding="UTF-8"?>
<!--
	Generate JSON from the EAR XML
	Demonstration sample XSLT
-->

<xsl:stylesheet version="1.0" 
	xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
	xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
	xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage"
	xmlns:er="http://www.easa.europa.eu/erules-export">

<xsl:param name="debug" select="'true'"/>
	
<xsl:output method="text" encoding="UTF-8" omit-xml-declaration="yes" indent="no"/>

<xsl:strip-space elements="*"/>
	
<xsl:template match="pkg:package">
	<xsl:apply-templates/>
</xsl:template>

<xsl:template match="pkg:part">
	<xsl:choose>
		<xsl:when test="descendant::er:document">
			<xsl:apply-templates/>
		</xsl:when>
		<xsl:otherwise>
			<!-- delete other parts by doing nothing here -->
		</xsl:otherwise>
	</xsl:choose>
</xsl:template>
	
<xsl:template match="pkg:xmlData">
	<xsl:apply-templates/>
</xsl:template>

<!--The special JSON {} and [] are inserted
	and we make sure to use the "," to separate things, for example by testing if we are on the LAST metadata field, EASACategory,
	since no "," is needed after this-->
<xsl:template match="er:document"> 
{"document":
	[
		{"doc-metadata":
		{<xsl:for-each select="@*">"<xsl:value-of select="name()"/>":"<xsl:value-of select="string()"/>"<xsl:if test="name()!='EASACategory'">,</xsl:if></xsl:for-each>}
		},
		{"doc-content":
			[
				<xsl:apply-templates/>
			]
		}
	]
}
</xsl:template>	

<xsl:template match="er:toc">		
{"toc":
	[	
	<xsl:apply-templates/>
	]
}<xsl:if test="following-sibling::*">,</xsl:if>
</xsl:template>
	
<xsl:template match="er:heading">		
{"heading":"<xsl:value-of select="@title"/>"}<xsl:if test="following-sibling::*">,</xsl:if>
</xsl:template>
	
<xsl:template match="er:topic">
<xsl:variable name="sdt-id" select="@sdt-id"/>
{"topic":
	[
		{"topic-metadata":
			{<xsl:for-each select="@*">"<xsl:value-of select="name()"/>":"<xsl:value-of select="string()"/>"<xsl:if test="name()!='EASACategory'">,</xsl:if></xsl:for-each>}
		},
		{"topic-content":
			[
			<xsl:for-each select="//w:sdt[w:sdtPr/w:id/@w:val=$sdt-id]/w:sdtContent/w:p">
				<xsl:if test="not(normalize-space(.)='')">
					{"para":"<xsl:value-of select="normalize-space(.)"/>"}<xsl:if test="following-sibling::w:p[normalize-space(.)!= '']">,</xsl:if>
				</xsl:if>	
			</xsl:for-each>
			]
		}
	]
}<xsl:if test="following-sibling::*">,</xsl:if>	
</xsl:template>	
</xsl:stylesheet>
