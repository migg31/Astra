<?xml version="1.0" encoding="UTF-8"?>
<!--
	Generate CSV for Excel data import, using # as delimiter
	NOTE: Use output from the RemovePartsAndElements-WithContent as input for this XSLT
	Demonstration sample XSLT
-->

<xsl:stylesheet version="1.0" 
	xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
	xmlns:er="http://www.easa.europa.eu/erules-export"
	exclude-result-prefixes="er">

<!-- note that method=text is selected, as output from this sheet is not xml or html -->
<xsl:output method="text" encoding="UTF-8" omit-xml-declaration="yes" indent="no"/>
	
<!-- the first line sets up the field names/Excel column names chosen for this example
	the second line has two for-each loops, the first ensures exactly one Excel row per para, the inner for-each just cycles through 
	all the metadata for the topic. Only the 6 chosen metadatafields are processed. As the output is text, line-feeds and spaces are
	important, hence the not so nice formatting of the code.
-->
<xsl:template match="er:document">SourceTitle#ERulesId#Domain#EntryIntoForceDate#RegulatorySource#Paragraph#
<xsl:for-each select="//para"><xsl:for-each select="ancestor::er:topic/@*"><xsl:if test="name()='source-title' or name()='ERulesId' or name()='Domain' or name()='EntryIntoForceDate' or name()='RegulatorySource'"><xsl:value-of select="string()"/>#</xsl:if></xsl:for-each><xsl:value-of select="normalize-space()"/>#
</xsl:for-each>
</xsl:template>
	
</xsl:stylesheet>
